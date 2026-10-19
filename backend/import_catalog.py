"""Importe metadados do catálogo legado, sem executar o arquivo de origem.

O importador nunca importa saldos, custos, pedidos, usuários ou credenciais.
Valide primeiro: python -m backend.import_catalog --dry-run
"""

import argparse
import ast
import csv
import json
import re
from io import StringIO
from pathlib import Path
import unicodedata


DEFAULT_SOURCE = Path(__file__).with_name("import_data.py")


def read_catalog(source):
    """Leia apenas o literal raw_data e descarte códigos com dados ambíguos."""
    tree = ast.parse(Path(source).read_text(encoding="utf-8-sig"), filename=str(source))
    literals = [
        node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "raw_data" for target in node.targets)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    ]
    if len(literals) != 1:
        raise ValueError("A origem deve conter exatamente uma atribuição literal de texto a raw_data.")
    reader = csv.reader(StringIO(literals[0].strip()), delimiter="\t")
    header = next(reader, [])
    if [value.strip().upper() for value in header[:3]] != ["CÓDIGO", "SEÇÃO", "DESCRIÇÃO"]:
        raise ValueError("Cabeçalho esperado: CÓDIGO, SEÇÃO e DESCRIÇÃO, separados por tabulação.")
    catalog, ambiguous = {}, set()
    invalid = duplicate = 0
    for row in reader:
        if len(row) < 3:
            invalid += 1
            continue
        code, section, name = (unicodedata.normalize("NFC", value.strip()) for value in row[:3])
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,20}", code) or not name or len(name) > 150 or len(section) > 100:
            invalid += 1
            continue
        item = {"codigo": code, "nome": name, "secao": section}
        if code in catalog:
            duplicate += 1
            previous = catalog[code]
            if previous["nome"].casefold() != name.casefold() or previous["secao"].casefold() != section.casefold():
                ambiguous.add(code)
        else:
            catalog[code] = item
    for code in ambiguous:
        catalog.pop(code, None)
    return list(catalog.values()), {"invalidas": invalid, "duplicadas": duplicate, "codigos_ambiguos": len(ambiguous)}


def import_catalog(connection, catalog):
    """Insira somente novos produtos/seções em uma única transação."""
    result = {"produtos": 0, "secoes": 0, "existentes": 0}
    if connection.in_transaction:
        raise RuntimeError("A importação precisa iniciar fora de outra transação.")
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        existing = {row[0] for row in connection.execute("SELECT id FROM produtos")}
        sections = {unicodedata.normalize("NFC", row[1]).casefold(): row[0] for row in connection.execute("SELECT id,nome FROM secoes")}
        for item in catalog:
            if item["codigo"] in existing:
                result["existentes"] += 1
                continue
            section_id = None
            if item["secao"]:
                key = item["secao"].casefold()
                section_id = sections.get(key)
                if section_id is None:
                    section_id = connection.execute("INSERT INTO secoes(nome) VALUES(?)", (item["secao"],)).lastrowid
                    sections[key] = section_id
                    result["secoes"] += 1
            connection.execute("INSERT INTO produtos(id,nome,secao_id) VALUES(?,?,?)", (item["codigo"], item["nome"], section_id))
            existing.add(item["codigo"])
            result["produtos"] += 1
        if result["produtos"]:
            connection.execute(
                "INSERT INTO auditoria(acao,entidade,entidade_id,detalhes) VALUES(?,?,?,?)",
                ("importar", "catalogo", "local", json.dumps(result, ensure_ascii=False)),
            )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="Arquivo Python legado que contém o literal raw_data")
    parser.add_argument("--dry-run", action="store_true", help="Valide o arquivo sem abrir ou alterar o banco")
    args = parser.parse_args()
    try:
        catalog, stats = read_catalog(args.source)
    except (OSError, SyntaxError, ValueError) as error:
        parser.exit(1, f"Catálogo inválido: {error}\n")
    print(f"Catálogo válido: {len(catalog)} produtos; linhas inválidas: {stats['invalidas']}; repetições: {stats['duplicadas']}; códigos ambíguos ignorados: {stats['codigos_ambiguos']}.")
    if args.dry_run:
        print("Simulação concluída. Nenhum banco foi aberto e nenhum dado foi alterado.")
        return
    from backend.app import create_app
    from backend.db import get_db

    app = create_app()
    with app.app_context():
        try:
            result = import_catalog(get_db(), catalog)
        except Exception:
            get_db().rollback()
            raise
    print(f"Importação concluída: {result['produtos']} produtos e {result['secoes']} seções adicionados; {result['existentes']} produtos existentes preservados.")
    print("Saldos e custos permanecem inalterados. Cadastre entradas reais no ERP antes de consumir os itens.")


if __name__ == "__main__":
    main()
