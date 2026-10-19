"""Safety and persistence checks for the supported local tooling."""

import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from backend.db import SCHEMA
from backend.import_catalog import import_catalog, read_catalog


class CatalogReaderTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="erp-tools-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / "legacy.py"

    def source_with(self, rows, prefix=""):
        content = "CÓDIGO\tSEÇÃO\tDESCRIÇÃO\tESTOQUE\n" + rows
        self.source.write_text(prefix + "\nraw_data = " + repr(content) + "\n", encoding="utf-8")
        return self.source

    def test_source_is_not_executed_and_historical_balance_is_not_imported(self):
        marker = self.root / "must-not-exist"
        source = self.source_with(
            "000123\tLimpeza\tProduto\t9876\n",
            "from pathlib import Path\nPath(" + repr(str(marker)) + ").touch()",
        )
        catalog, stats = read_catalog(source)
        self.assertFalse(marker.exists())
        self.assertEqual(catalog, [{"codigo": "000123", "nome": "Produto", "secao": "Limpeza"}])
        self.assertEqual(stats["invalidas"], 0)

    def test_conflicting_product_codes_are_omitted_instead_of_overwritten(self):
        source = self.source_with(
            "001\tLimpeza\tProduto A\t1\n"
            "001\tLimpeza\tProduto A\t2\n"
            "002\t\tProduto B\t1\n"
            "002\t\tProduto diferente\t1\n"
        )
        catalog, stats = read_catalog(source)
        self.assertEqual([item["codigo"] for item in catalog], ["001"])
        self.assertEqual(stats["codigos_ambiguos"], 1)
        self.assertEqual(stats["duplicadas"], 2)

    def test_nonliteral_source_and_invalid_header_are_rejected(self):
        self.source.write_text("raw_data = str('dynamic text')", encoding="utf-8")
        with self.assertRaises(ValueError):
            read_catalog(self.source)
        self.source.write_text("raw_data = 'unexpected header'", encoding="utf-8")
        with self.assertRaises(ValueError):
            read_catalog(self.source)


class CatalogTransactionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="erp-import-")
        self.addCleanup(self.directory.cleanup)
        self.connection = sqlite3.connect(Path(self.directory.name) / "test.sqlite3")
        self.addCleanup(self.connection.close)
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.executescript(SCHEMA)
        self.connection.execute("INSERT INTO lojas(id,nome,sigla) VALUES(1,'Teste','TST')")
        self.connection.execute("INSERT INTO secoes(nome) VALUES('Limpeza')")
        self.connection.execute("INSERT INTO produtos(id,nome,custo,ativo) VALUES('001','Nome operacional',9.99,0)")
        self.connection.execute("INSERT INTO estoque VALUES('001',1,7.5)")
        self.connection.commit()
        self.catalog = [
            {"codigo": "001", "nome": "Nome legado", "secao": "LIMPEZA"},
            {"codigo": "002", "nome": "Produto novo", "secao": "LIMPEZA"},
        ]

    def test_import_preserves_existing_operation_and_is_idempotent(self):
        first = import_catalog(self.connection, self.catalog)
        self.assertEqual(first, {"produtos": 1, "secoes": 0, "existentes": 1})
        self.assertEqual(self.connection.execute("SELECT nome,custo,ativo FROM produtos WHERE id='001'").fetchone(),
                         ("Nome operacional", 9.99, 0))
        self.assertEqual(self.connection.execute("SELECT quantidade FROM estoque WHERE produto_id='001'").fetchone()[0], 7.5)
        self.assertEqual(self.connection.execute("SELECT custo FROM produtos WHERE id='002'").fetchone()[0], 0)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM estoque WHERE produto_id='002'").fetchone()[0], 0)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM movimentacoes").fetchone()[0], 0)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM auditoria").fetchone()[0], 1)
        second = import_catalog(self.connection, self.catalog)
        self.assertEqual(second, {"produtos": 0, "secoes": 0, "existentes": 2})
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM auditoria").fetchone()[0], 1)

    def test_failure_rolls_back_both_product_and_new_section(self):
        self.connection.execute("CREATE TRIGGER reject_catalog_audit BEFORE INSERT ON auditoria BEGIN SELECT RAISE(ABORT,'test rollback'); END")
        self.connection.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            import_catalog(self.connection, [{"codigo": "NEW", "nome": "Produto novo", "secao": "Seção nova"}])
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM produtos WHERE id='NEW'").fetchone()[0], 0)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM secoes WHERE nome='Seção nova'").fetchone()[0], 0)


class DocumentedBackupTests(unittest.TestCase):
    def test_documented_backup_contains_committed_rows_still_in_wal(self):
        readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
        script = readme.split("python - <<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
        with tempfile.TemporaryDirectory(prefix="erp-backup-") as directory:
            root = Path(directory)
            database = root / "active.sqlite3"
            source = sqlite3.connect(database)
            try:
                source.execute("PRAGMA journal_mode=WAL")
                source.execute("PRAGMA wal_autocheckpoint=0")
                source.execute("CREATE TABLE persistence_test (value TEXT)")
                source.execute("INSERT INTO persistence_test VALUES('latest committed row')")
                source.commit()
                self.assertTrue(Path(str(database) + "-wal").is_file())
                environment = dict(os.environ, ERP_DATABASE=str(database), ERP_BACKUP_DIR=str(root / "backups"))
                result = subprocess.run([sys.executable, "-c", script], env=environment,
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                backup = next((root / "backups").glob("erp-*.sqlite3"))
                target = sqlite3.connect(backup)
                try:
                    self.assertEqual(target.execute("PRAGMA quick_check").fetchone()[0], "ok")
                    self.assertEqual(target.execute("SELECT value FROM persistence_test").fetchone()[0], "latest committed row")
                finally:
                    target.close()
            finally:
                source.close()


if __name__ == "__main__":
    unittest.main()
