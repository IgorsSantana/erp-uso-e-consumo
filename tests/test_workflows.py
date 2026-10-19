"""Run with ``python -m unittest discover -s tests -v``.

Each test uses its own SQLite database and exercises real HTTP routes. No remote
database, SMTP account, network access, or third-party testing package is needed.
"""

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from backend.app import create_app


class ERPWorkflowTests(unittest.TestCase):
    password = "SenhaSegura2026!"

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="erp-test-")
        self.addCleanup(self.directory.cleanup)
        self.database = str(Path(self.directory.name) / "erp.sqlite3")
        self.app = create_app({
            "TESTING": True,
            "DATABASE": self.database,
            "SECRET_KEY": "test-only-secret-key",
        })
        self.client = self.app.test_client()
        response = self.client.post("/api/setup", json={
            "nome": "Administrador de teste",
            "username": "admin_teste",
            "password": self.password,
        })
        self.assertIn(response.status_code, (200, 201), response.get_data(as_text=True))

    def write(self, method, path, data=None, client=None):
        client = client or self.client
        session = client.get("/api/session").get_json()
        return client.open(path, method=method, json=data,
                           headers={"X-CSRF-Token": session["csrf_token"]})

    def successful(self, response):
        self.assertIn(response.status_code, (200, 201, 204),
                      response.get_data(as_text=True))
        return response.get_json(silent=True)

    def rejected(self, response, statuses=(400, 403, 404, 409, 422)):
        self.assertIn(response.status_code, statuses,
                      response.get_data(as_text=True))
        self.assertIsInstance(response.get_json(), dict)
        self.assertIn("error", response.get_json())

    def create(self, collection, data):
        body = self.successful(self.write("POST", "/api/" + collection, data))
        self.assertIn("id", body)
        return body["id"]

    def fixture(self):
        """A small independent catalog suitable for stock/order/quote tests."""
        self.section = self.create("secoes", {"nome": "Limpeza de teste"})
        self.origin = self.create("lojas", {"nome": "Matriz de teste", "sigla": "TMT"})
        self.destination = self.create("lojas", {"nome": "Filial de teste", "sigla": "TFL"})
        self.product = "90101"
        self.other_product = "90102"
        for product, name in ((self.product, "Detergente de teste"),
                              (self.other_product, "Papel de teste")):
            self.create("produtos", {
                "id": product, "nome": name, "secao_id": self.section,
                "unidade": "UN", "custo": 12.5,
                "estoque_minimo": 2, "estoque_maximo": 100,
            })

    def move(self, quantity, kind="Entrada", product=None, origin=None,
             destination=None):
        data = {"tipo": kind, "produto_id": product or self.product,
                "loja_id": origin or self.origin, "quantidade": quantity,
                "motivo": "Movimentação de teste"}
        if destination is not None:
            data["loja_destino_id"] = destination
        return self.write("POST", "/api/movimentacoes", data)

    def stock(self, product, store):
        response = self.client.get("/api/estoque")
        self.assertEqual(response.status_code, 200)
        rows = response.get_json()
        return sum(float(row["quantidade"]) for row in rows
                   if str(row["produto_id"]) == str(product)
                   and str(row["loja_id"]) == str(store))

    def order(self, items=None):
        return self.create("pedidos", {
            "loja_id": self.destination,
            "loja_origem_id": self.origin,
            "observacoes": "Abastecer filial de teste",
            "itens": items or [{"produto_id": self.product, "quantidade": 4}],
        })

    def set_order_status(self, order, status):
        return self.write("POST", f"/api/pedidos/{order}/status", {"status": status})

    def quote(self, products=None):
        suppliers = [self.create("fornecedores", {
            "nome_fantasia": name, "email": email,
        }) for name, email in (("Fornecedor teste A", "a@example.test"),
                               ("Fornecedor teste B", "b@example.test"))]
        quote = self.create("cotacoes", {
            "titulo": "Reposição de materiais de teste", "fornecedores": suppliers,
            "itens": [{"produto_id": p, "quantidade": 3}
                      for p in (products or [self.product])],
        })
        detail = self.client.get(f"/api/cotacoes/{quote}").get_json()
        tokens = {str(row["id"]): row["token"] for row in detail["fornecedores"]}
        return quote, suppliers, [tokens[str(supplier)] for supplier in suppliers]

    def bid(self, token, price, product=None, **extra):
        return self.app.test_client().post(f"/api/portal-fornecedor/{token}", json={
            "respostas": [{"produto_id": product or self.product,
                           "preco": price, **extra}],
            "observacoes": "Proposta de teste",
        })

    def test_first_setup_is_single_use_and_does_not_leak_password_hash(self):
        session = self.client.get("/api/session").get_json()
        self.assertFalse(session["setup_required"])
        self.assertEqual(session["user"]["username"], "admin_teste")
        self.assertNotIn("password", session["user"])
        self.assertNotIn("senha_hash", session["user"])
        self.rejected(self.app.test_client().post("/api/setup", json={
            "nome": "Outro administrador", "username": "intruso",
            "password": self.password,
        }))

    def test_unauthenticated_access_and_logout_revoke_session(self):
        anonymous = self.app.test_client()
        for path in ("/api/produtos", "/api/usuarios", "/api/estoque", "/api/pedidos"):
            with self.subTest(path=path):
                self.rejected(anonymous.get(path), (401,))
        self.successful(self.write("POST", "/api/logout", {}))
        self.rejected(self.client.get("/api/produtos"), (401,))
        self.assertIsNone(self.client.get("/api/session").get_json()["user"])

    def test_logout_revokes_copied_cookie_without_ending_other_sessions(self):
        other = self.app.test_client()
        self.successful(other.post('/api/login', json={'username':'admin_teste','password':self.password}))
        cookie = self.client.get_cookie('session').value
        self.successful(self.write('POST','/api/logout',{}))
        replay = self.app.test_client()
        replay.set_cookie('session',cookie)
        self.assertIsNone(replay.get('/api/session').get_json()['user'])
        self.assertEqual(replay.get('/api/produtos').status_code,401)
        self.assertEqual(other.get('/api/produtos').status_code,200)

    def test_password_change_validates_current_password_and_revokes_other_sessions(self):
        other = self.app.test_client()
        self.successful(other.post('/api/login',json={'username':'admin_teste','password':self.password}))
        payload={'current_password':'wrong password','new_password':'NovaSenhaSegura2026!'}
        self.rejected(self.write('POST','/api/account/password',payload),(403,))
        self.assertEqual(other.get('/api/produtos').status_code,200)
        payload['current_password']=self.password
        self.successful(self.write('POST','/api/account/password',payload))
        self.assertEqual(self.client.get('/api/produtos').status_code,200)
        self.assertEqual(other.get('/api/produtos').status_code,401)
        fresh=self.app.test_client()
        self.assertEqual(fresh.post('/api/login',json={'username':'admin_teste','password':self.password}).status_code,401)
        self.successful(fresh.post('/api/login',json={'username':'admin_teste','password':payload['new_password']}))

    def test_recorded_consumption_keeps_historical_unit_cost(self):
        self.fixture()
        self.successful(self.move(5))
        self.successful(self.move(2,kind='Saida'))
        self.successful(self.write('PUT',f'/api/produtos/{self.product}',{'custo':99}))
        report=self.client.get('/api/dashboard').get_json()
        self.assertEqual(report['consumo_por_secao'][0]['valor'],25)
        moves=self.client.get('/api/movimentacoes').get_json()
        self.assertEqual(moves[0]['custo_unitario'],12.5)

    def test_optional_quote_deadline_and_delivery_are_accepted_with_four_decimal_prices(self):
        self.fixture()
        supplier=self.create('fornecedores',{'nome_fantasia':'Precision supplier'})
        quote=self.create('cotacoes',{'titulo':'Sem prazo','data_limite':None,'itens':[{'produto_id':self.product,'quantidade':1}],'fornecedores':[supplier]})
        token=self.client.get(f'/api/cotacoes/{quote}').get_json()['fornecedores'][0]['token']
        public=self.app.test_client()
        self.successful(public.post(f'/api/portal-fornecedor/{token}',json={'respostas':[{'produto_id':self.product,'preco':12.3456,'prazo_entrega':None}]}))
        saved=public.get(f'/api/portal-fornecedor/{token}').get_json()
        self.assertEqual(saved['respostas'][self.product],12.3456)
        self.assertEqual(saved['respostas_detalhes'][self.product]['prazo_entrega'],0)

    def test_login_rejects_wrong_password_and_accepts_valid_credentials(self):
        client = self.app.test_client()
        self.rejected(client.post("/api/login", json={
            "username": "admin_teste", "password": "senha-incorreta",
        }), (401,))
        self.successful(client.post("/api/login", json={
            "username": "admin_teste", "password": self.password,
        }))
        self.assertEqual(client.get("/api/produtos").status_code, 200)

    def test_authenticated_writes_require_csrf_token(self):
        for headers in ({}, {"X-CSRF-Token": "token-invalido"}):
            with self.subTest(headers=headers):
                self.rejected(self.client.post("/api/secoes",
                    json={"nome": "Sem autorização CSRF"}, headers=headers), (403,))

    def test_new_environment_dashboard_is_usable_before_catalog_setup(self):
        response = self.client.get("/api/dashboard")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        data = response.get_json()
        self.assertEqual(float(data["valor_estoque"]), 0)
        self.assertEqual(data["produtos"], 0)
        self.assertEqual(data["alertas"], [])

    def test_static_server_never_exposes_source_database_or_git(self):
        anonymous = self.app.test_client()
        for path in ("/backend/db.py", "/backend/app.py", "/.git/config",
                     "/database_schema.sql", "/tests/test_workflows.py",
                     "/../backend/db.py", "/%2e%2e/backend/db.py"):
            with self.subTest(path=path):
                response = anonymous.get(path)
                self.assertIn(response.status_code, (403, 404))
        with anonymous.get("/") as response:
            self.assertEqual(response.status_code, 200)

    def test_operational_role_cannot_manage_users_or_catalog(self):
        self.create("usuarios", {"nome": "Operador", "username": "operador_teste",
                                "password": self.password, "nivel_acesso": "Operacional"})
        operator = self.app.test_client()
        self.successful(operator.post("/api/login", json={
            "username": "operador_teste", "password": self.password,
        }))
        self.assertEqual(operator.get("/api/produtos").status_code, 200)
        self.rejected(operator.get("/api/usuarios"), (403,))
        self.rejected(operator.get("/api/compras"), (403,))
        self.rejected(self.write("POST", "/api/compras/1/receber", {}, operator), (403,))
        self.rejected(self.write("POST", "/api/secoes", {"nome": "Indevida"}, operator), (403,))
        self.rejected(self.write("POST", "/api/usuarios", {
            "nome": "Administrador indevido", "username": "novo_admin",
            "password": self.password, "nivel_acesso": "Admin",
        }, operator), (403,))

    def test_catalog_creation_update_and_input_validation(self):
        self.fixture()
        self.successful(self.write("PUT", f"/api/produtos/{self.product}", {
            "nome": "Detergente atualizado", "secao_id": self.section,
            "unidade": "L", "custo": 14.75,
            "estoque_minimo": 3, "estoque_maximo": 80,
        }))
        products = self.client.get("/api/produtos").get_json()
        row = next(row for row in products if str(row["id"]) == self.product)
        self.assertEqual(row["nome"], "Detergente atualizado")
        self.assertAlmostEqual(float(row["custo"]), 14.75)
        for invalid in ({"id": "99901", "nome": "", "custo": 1},
                        {"id": "99902", "nome": "Inválido", "custo": -1},
                        {"id": "99903", "nome": "Inválido", "custo": "NaN"},
                        {"id": "99904", "nome": "Inválido", "custo": "Infinity"},
                        {"id": "99905", "nome": "Inválido", "custo": 1,
                         "estoque_minimo": 20, "estoque_maximo": 10}):
            with self.subTest(invalid=invalid):
                self.rejected(self.write("POST", "/api/produtos", invalid))

    def test_stock_entry_exit_transfer_and_immutable_history(self):
        self.fixture()
        self.successful(self.move(20))
        self.successful(self.move(3, "Saida"))
        self.successful(self.move(5, "Transferencia", destination=self.destination))
        self.assertEqual(self.stock(self.product, self.origin), 12)
        self.assertEqual(self.stock(self.product, self.destination), 5)
        history = self.client.get("/api/movimentacoes").get_json()
        self.assertGreaterEqual(len(history), 3)
        self.assertTrue(any(row.get("motivo") == "Movimentação de teste" for row in history))

    def test_insufficient_stock_and_invalid_quantities_never_change_balance(self):
        self.fixture()
        self.successful(self.move(5))
        for quantity in (6, -1, 0, "NaN", "Infinity", "texto"):
            with self.subTest(quantity=quantity):
                self.rejected(self.move(quantity, "Saida"))
                self.assertEqual(self.stock(self.product, self.origin), 5)
        self.rejected(self.move(6, "Transferencia", destination=self.destination))
        self.assertEqual(self.stock(self.product, self.origin), 5)
        self.assertEqual(self.stock(self.product, self.destination), 0)

    def test_transfer_to_same_store_is_rejected(self):
        self.fixture()
        self.successful(self.move(5))
        self.rejected(self.move(2, "Transferencia", destination=self.origin))
        self.assertEqual(self.stock(self.product, self.origin), 5)

    def test_concurrent_withdrawals_cannot_oversell_the_same_balance(self):
        self.fixture()
        self.successful(self.move(5))
        clients = [self.app.test_client(), self.app.test_client()]
        tokens = []
        for client in clients:
            self.successful(client.post("/api/login", json={
                "username": "admin_teste", "password": self.password,
            }))
            tokens.append(client.get("/api/session").get_json()["csrf_token"])

        def withdraw(index):
            return clients[index].post("/api/movimentacoes", json={
                "tipo": "Saida", "produto_id": self.product,
                "loja_id": self.origin, "quantidade": 4,
                "motivo": "Retirada concorrente de teste",
            }, headers={"X-CSRF-Token": tokens[index]})

        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(withdraw, range(2)))
        self.assertEqual(sum(r.status_code in (200, 201) for r in responses), 1,
                         [r.get_data(as_text=True) for r in responses])
        for response in responses:
            if response.status_code not in (200, 201):
                self.rejected(response)
        self.assertEqual(self.stock(self.product, self.origin), 1)

    def test_physical_count_records_balance_and_is_atomic(self):
        self.fixture()
        self.successful(self.move(5))
        self.successful(self.write("POST", "/api/contagens", {
            "loja_id": self.origin, "motivo": "Conferência física de teste",
            "itens": [{"produto_id": self.product, "quantidade": 8}],
        }))
        self.assertEqual(self.stock(self.product, self.origin), 8)
        self.rejected(self.write("POST", "/api/contagens", {
            "loja_id": self.origin, "motivo": "Contagem inválida",
            "itens": [{"produto_id": self.product, "quantidade": 2},
                      {"produto_id": self.other_product, "quantidade": -1}],
        }))
        self.assertEqual(self.stock(self.product, self.origin), 8)

    def test_requisition_approval_fulfillment_transfers_once(self):
        self.fixture()
        self.successful(self.move(12))
        order = self.order()
        self.assertEqual(self.stock(self.product, self.origin), 12)
        self.rejected(self.set_order_status(order, "Atendido"))
        self.successful(self.set_order_status(order, "Aprovado"))
        self.assertEqual(self.stock(self.product, self.origin), 12)
        self.successful(self.set_order_status(order, "Atendido"))
        self.assertEqual(self.stock(self.product, self.origin), 8)
        self.assertEqual(self.stock(self.product, self.destination), 4)
        self.rejected(self.set_order_status(order, "Atendido"))
        self.assertEqual(self.stock(self.product, self.origin), 8)
        self.assertEqual(self.stock(self.product, self.destination), 4)

    def test_requisition_with_one_short_item_fails_atomically(self):
        self.fixture()
        self.successful(self.move(10))
        self.successful(self.move(1, product=self.other_product))
        order = self.order([
            {"produto_id": self.product, "quantidade": 4},
            {"produto_id": self.other_product, "quantidade": 2},
        ])
        self.successful(self.set_order_status(order, "Aprovado"))
        self.rejected(self.set_order_status(order, "Atendido"))
        self.assertEqual(self.stock(self.product, self.origin), 10)
        self.assertEqual(self.stock(self.other_product, self.origin), 1)
        self.assertEqual(self.stock(self.product, self.destination), 0)

    def test_cancelled_requisition_cannot_be_approved(self):
        self.fixture()
        order = self.order()
        self.successful(self.set_order_status(order, "Cancelado"))
        self.rejected(self.set_order_status(order, "Aprovado"))

    def test_supplier_token_is_public_but_not_a_general_api_credential(self):
        self.fixture()
        quote, suppliers, tokens = self.quote()
        public = self.app.test_client()
        response = public.get(f"/api/portal-fornecedor/{tokens[0]}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.get_json()["itens"]), 1)
        self.rejected(public.get("/api/cotacoes"), (401,))
        self.rejected(public.get("/api/portal-fornecedor/token-inexistente"), (404,))
        self.assertNotEqual(tokens[0], tokens[1])

    def test_supplier_cannot_bid_on_unrequested_product_or_replace_valid_bid_with_invalid(self):
        self.fixture()
        quote, suppliers, tokens = self.quote()
        self.successful(self.bid(tokens[0], 9.25))
        self.rejected(self.bid(tokens[0], 1, product=self.other_product))
        portal = self.app.test_client().get(f"/api/portal-fornecedor/{tokens[0]}").get_json()
        self.assertAlmostEqual(float(portal["respostas"][self.product]), 9.25)

    def test_supplier_prices_must_be_finite_positive_numbers(self):
        self.fixture()
        quote, suppliers, tokens = self.quote()
        for price in (-1, 0, "NaN", "Infinity", "texto"):
            with self.subTest(price=price):
                self.rejected(self.bid(tokens[0], price))

    def test_quotation_selects_lowest_bid_without_revaluing_stock_and_freezes_response(self):
        self.fixture()
        quote, suppliers, tokens = self.quote()
        self.successful(self.bid(tokens[0], 10.5))
        self.successful(self.bid(tokens[1], 8.75))
        self.successful(self.write("POST", f"/api/cotacoes/{quote}/encerrar", {}))
        detail = self.client.get(f"/api/cotacoes/{quote}").get_json()
        self.assertEqual(detail["status"], "Encerrada")
        winners = [bid for bid in detail["respostas"] if bid["vencedor"]]
        self.assertEqual(len(winners), 1)
        self.assertEqual(str(winners[0]["fornecedor_id"]), str(suppliers[1]))
        self.assertAlmostEqual(float(winners[0]["preco"]), 8.75)
        products = self.client.get("/api/produtos").get_json()
        product = next(p for p in products if str(p["id"]) == self.product)
        self.assertAlmostEqual(float(product["custo"]), 12.5)
        self.rejected(self.bid(tokens[0], 7.5))
        self.rejected(self.write("POST", f"/api/cotacoes/{quote}/encerrar", {}))

    def test_quotation_cannot_close_without_priced_response_for_every_item(self):
        self.fixture()
        quote, suppliers, tokens = self.quote([self.product, self.other_product])
        self.successful(self.app.test_client().post(f"/api/portal-fornecedor/{tokens[0]}", json={
            "respostas": [
                {"produto_id": self.product, "preco": 10},
                {"produto_id": self.other_product, "preco": 0, "indisponivel": True},
            ],
        }))
        self.rejected(self.write("POST", f"/api/cotacoes/{quote}/encerrar", {}))
        detail = self.client.get(f"/api/cotacoes/{quote}").get_json()
        self.assertEqual(detail["status"], "Aberta")

    def test_purchase_receipt_updates_stock_cost_and_cannot_be_repeated(self):
        self.fixture()
        supplier = self.create("fornecedores", {"nome_fantasia": "Fornecedor da compra"})
        purchase = self.create("compras", {
            "fornecedor_id": supplier, "loja_id": self.origin,
            "itens": [{"produto_id": self.product, "quantidade": 4, "custo_unitario": 8.755}],
        })
        self.assertEqual(self.stock(self.product, self.origin), 0)
        self.successful(self.write("POST", f"/api/compras/{purchase}/receber", {}))
        self.assertEqual(self.stock(self.product, self.origin), 4)
        products = self.client.get("/api/produtos").get_json()
        product = next(p for p in products if str(p["id"]) == self.product)
        self.assertAlmostEqual(float(product["custo"]), 8.76)
        self.rejected(self.write("POST", f"/api/compras/{purchase}/receber", {}))
        self.rejected(self.write("POST", f"/api/compras/{purchase}/cancelar", {}))
        self.assertEqual(self.stock(self.product, self.origin), 4)

    def test_cancelled_purchase_cannot_be_received(self):
        self.fixture()
        supplier = self.create("fornecedores", {"nome_fantasia": "Fornecedor da compra"})
        purchase = self.create("compras", {
            "fornecedor_id": supplier, "loja_id": self.origin,
            "itens": [{"produto_id": self.product, "quantidade": 4, "custo_unitario": 8}],
        })
        self.successful(self.write("POST", f"/api/compras/{purchase}/cancelar", {}))
        self.rejected(self.write("POST", f"/api/compras/{purchase}/receber", {}))
        self.assertEqual(self.stock(self.product, self.origin), 0)

    def test_purchase_receipt_rolls_back_if_one_product_is_inactive(self):
        self.fixture()
        supplier = self.create("fornecedores", {"nome_fantasia": "Fornecedor da compra"})
        purchase = self.create("compras", {
            "fornecedor_id": supplier, "loja_id": self.origin,
            "itens": [{"produto_id": pid, "quantidade": 4, "custo_unitario": 8}
                      for pid in (self.product, self.other_product)],
        })
        self.successful(self.write("PUT", f"/api/produtos/{self.other_product}", {"ativo": False}))
        self.rejected(self.write("POST", f"/api/compras/{purchase}/receber", {}))
        self.assertEqual(self.stock(self.product, self.origin), 0)
        purchases = self.client.get("/api/compras").get_json()
        self.assertEqual(next(p for p in purchases if p["id"] == purchase)["status"], "Pendente")
        products = self.client.get("/api/produtos").get_json()
        self.assertEqual(float(next(p for p in products if p["id"] == self.product)["custo"]), 12.5)

    def test_closed_quote_generates_one_purchase_per_winning_supplier_only_once(self):
        self.fixture()
        quote, suppliers, tokens = self.quote([self.product, self.other_product])
        for token, prices in zip(tokens, ((9, 20), (10, 15))):
            self.successful(self.app.test_client().post(f"/api/portal-fornecedor/{token}", json={
                "respostas": [{"produto_id": pid, "preco": price}
                              for pid, price in zip((self.product, self.other_product), prices)],
            }))
        self.rejected(self.write("POST", f"/api/cotacoes/{quote}/compras", {"loja_id": self.origin}))
        self.successful(self.write("POST", f"/api/cotacoes/{quote}/encerrar", {}))
        created = self.successful(self.write("POST", f"/api/cotacoes/{quote}/compras", {"loja_id": self.origin}))
        self.assertEqual(len(created["ids"]), 2)
        purchases = self.client.get("/api/compras").get_json()
        self.assertEqual({p["fornecedor_id"] for p in purchases}, set(suppliers))
        self.assertTrue(all(p["cotacao_id"] == quote and len(p["itens"]) == 1 for p in purchases))
        self.rejected(self.write("POST", f"/api/cotacoes/{quote}/compras", {"loja_id": self.origin}))
        self.assertEqual(len(self.client.get("/api/compras").get_json()), 2)
        self.assertEqual(self.stock(self.product, self.origin), 0)
        for purchase in created["ids"]:
            self.successful(self.write("POST", f"/api/compras/{purchase}/receber", {}))
        self.assertEqual(self.stock(self.product, self.origin), 3)
        self.assertEqual(self.stock(self.other_product, self.origin), 3)

    def test_reference_catalog_is_seeded_once_and_deleted_entries_stay_deleted(self):
        stores = self.client.get("/api/lojas").get_json()
        sections = self.client.get("/api/secoes").get_json()
        self.assertGreaterEqual(len(stores), 7)
        self.assertGreaterEqual(len(sections), 8)
        deleted_store, deleted_section = stores[0]["id"], sections[0]["id"]
        self.successful(self.write("DELETE", f"/api/lojas/{deleted_store}"))
        self.successful(self.write("DELETE", f"/api/secoes/{deleted_section}"))
        restarted = create_app({"TESTING": True, "DATABASE": self.database,
                                "SECRET_KEY": "test-only-secret-key"})
        client = restarted.test_client()
        self.successful(client.post("/api/login", json={
            "username": "admin_teste", "password": self.password,
        }))
        self.assertNotIn(deleted_store, [row["id"] for row in client.get("/api/lojas").get_json()])
        self.assertNotIn(deleted_section, [row["id"] for row in client.get("/api/secoes").get_json()])

    def test_data_survives_application_restart(self):
        self.fixture()
        self.successful(self.move(9))
        restarted = create_app({"TESTING": True, "DATABASE": self.database,
                                "SECRET_KEY": "test-only-secret-key"})
        client = restarted.test_client()
        self.assertFalse(client.get("/api/session").get_json()["setup_required"])
        self.successful(client.post("/api/login", json={
            "username": "admin_teste", "password": self.password,
        }))
        rows = client.get("/api/estoque").get_json()
        stock = next(row for row in rows if str(row["produto_id"]) == self.product
                     and str(row["loja_id"]) == str(self.origin))
        self.assertEqual(float(stock["quantidade"]), 9)


if __name__ == "__main__":
    unittest.main()
