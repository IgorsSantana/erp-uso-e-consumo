"""Optional real-browser check using Playwright and a disposable local server.

Run ``python tests/browser_smoke.py`` after installing the Python Playwright
package. Set CHROMIUM_EXECUTABLE when the browser is outside /usr/bin/chromium.
No production data or existing administrator account is touched.
"""

import os
import io
import openpyxl
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app import create_app
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import WSGIRequestHandler, make_server


class QuietHandler(WSGIRequestHandler):
    def log_request(self, *args, **kwargs):
        pass


def run():
    with tempfile.TemporaryDirectory(prefix="erp-browser-") as directory:
        app = create_app({"TESTING": True,
                          "DATABASE": str(Path(directory) / "browser.sqlite3"),
                          "SECRET_KEY": "browser-test-only-key"})
        server = make_server("127.0.0.1", 0, app, threaded=True, request_handler=QuietHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_port}"
        try:
            with sync_playwright() as playwright:
                expect.set_options(timeout=15000)
                browser = playwright.chromium.launch(
                    executable_path=os.environ.get("CHROMIUM_EXECUTABLE", "/usr/bin/chromium"),
                    headless=True, args=["--no-sandbox"],
                )
                context = browser.new_context(viewport={"width": 1440, "height": 1000},
                                              locale="pt-BR", timezone_id="America/Sao_Paulo")
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(base_url)
                page.wait_for_url("**/login.html")
                page.get_by_label("Seu nome", exact=True).fill("Administrador de navegador")
                page.get_by_label("Usuário", exact=True).fill("admin_browser")
                page.get_by_label("Senha", exact=True).fill("NavegadorSeguro2026!")
                page.get_by_role("button", name="Criar conta e começar").click()
                expect(page.locator("#app-content h1")).to_be_visible()
                expect(page.locator("#auth-user-name")).to_have_text("Administrador de navegador")
                print("Browser: first administrator and empty dashboard passed.", flush=True)

                def api_post(path, body):
                    csrf = context.request.get(base_url + "/api/session").json()["csrf_token"]
                    response = context.request.post(base_url + path, data=body,
                        headers={"X-CSRF-Token": csrf})
                    assert response.ok, (path, response.status, response.text())
                    return response.json()

                section = api_post("/api/secoes", {"nome": "Seção do navegador"})["id"]
                origin = api_post("/api/lojas", {"nome": "Loja do navegador", "sigla": "NAV"})["id"]
                destination = api_post("/api/lojas", {"nome": "Filial do navegador", "sigla": "FNAV"})["id"]

                def navigate(view):
                    page.evaluate("view => { location.hash = view; }", view)
                    page.wait_for_function("view => window.App?.view === view && !document.getElementById('app-content').hasAttribute('aria-busy')", arg=view)
                    expect(page.locator("#app-content h1")).to_be_visible()
                    expect(page.locator("#app-content .error-state")).to_have_count(0)

                def stock(store):
                    result = context.request.get(base_url + "/api/estoque").json()
                    return next(float(row["quantidade"]) for row in result
                                if str(row["loja_id"]) == str(store) and row["produto_id"] == "990001")

                page.locator("#refresh-data").click()
                expect(page.locator("#app-content h1")).to_be_visible()
                page.locator('[data-view="produtos"]').click()
                page.get_by_role("button", name="+ Novo produto", exact=True).click()
                dialog = page.locator("#app-dialog")
                expect(dialog).to_be_visible()
                dialog.get_by_label("Código ERP").fill("990001")
                dialog.get_by_label("Nome do produto").fill("Produto criado no navegador")
                dialog.get_by_label("Seção", exact=True).select_option(str(section))
                dialog.get_by_label("Custo unitário (R$)").fill("10.50")
                dialog.get_by_role("button", name="Salvar registro", exact=True).click()
                expect(dialog).not_to_be_visible()
                expect(page.locator("#app-content")).to_contain_text("Produto criado no navegador")
                print("Browser: product creation form passed.", flush=True)

                assert page.locator('.data-table .cell-title').first.evaluate("element => parseFloat(getComputedStyle(element).fontSize)")>=16
                page.get_by_role('button',name='Importar planilha',exact=True).click()
                dialog.locator('#catalog-file').set_input_files({
                    'name':'produtos.csv','mimeType':'text/csv',
                    'buffer':'Código;Descrição;Seção;Custo\n990001;Nome que não deve sobrescrever;Teste;100\n990002;Produto importado pelo CSV;Papelaria;12,34'.encode('utf-8'),
                })
                dialog.get_by_role('button',name='Conferir arquivo',exact=True).click()
                expect(dialog).to_contain_text('1 novo(s) e 1 já cadastrado(s)')
                expect(dialog.get_by_role('button',name='Confirmar importação',exact=True)).to_be_enabled()
                dialog.get_by_role('button',name='Confirmar importação',exact=True).click()
                expect(dialog).not_to_be_visible()
                expect(page.locator('#app-content')).to_contain_text('Produto importado pelo CSV')
                expect(page.locator('#app-content')).to_contain_text('Produto criado no navegador')
                product_rows=context.request.get(base_url+'/api/produtos').json()
                assert next(p for p in product_rows if p['id']=='990001')['custo']==10.5
                assert next(p for p in product_rows if p['id']=='990002')['custo']==12.34
                print('Browser: spreadsheet CSV preview, import and existing-product preservation passed.',flush=True)
                excel=openpyxl.Workbook()
                excel.active.title='Cadastro Excel'
                excel.active.append(['Código','Descrição','Unidade'])
                excel.active.append(['990003','Produto importado do Excel','CX'])
                excel.active.append(['990004','Descrição conflitante A','UN'])
                excel.active.append(['990004','Descrição conflitante B','UN'])
                excel_buffer=io.BytesIO();excel.save(excel_buffer);excel.close()
                page.get_by_role('button',name='Importar planilha',exact=True).click()
                dialog.locator('#catalog-file').set_input_files({'name':'produtos.xlsx','mimeType':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','buffer':excel_buffer.getvalue()})
                dialog.get_by_role('button',name='Conferir arquivo',exact=True).click()
                expect(dialog).to_contain_text('1 código(s) separado(s) para revisão')
                expect(dialog).to_contain_text('990004')
                expect(dialog).to_contain_text('Produto importado do Excel')
                dialog.get_by_role('button',name='Confirmar importação',exact=True).click()
                expect(dialog).not_to_be_visible()
                expect(page.locator('#app-content')).to_contain_text('Produto importado do Excel')
                assert all(p['id']!='990004' for p in context.request.get(base_url+'/api/produtos').json())
                print('Browser: Excel upload, conflict review and confirmed import passed.',flush=True)


                navigate("estoque")
                page.get_by_role("button", name="+ Nova movimentação", exact=True).click()
                dialog.get_by_label("Tipo de movimentação").select_option("Entrada")
                dialog.locator('[name="produto_id"]').select_option("990001")
                dialog.get_by_label("Loja de origem / movimentação").select_option(str(origin))
                dialog.locator('[name="quantidade"]').fill("12")
                dialog.get_by_label("Motivo / documento").fill("Recebimento no navegador")
                dialog.get_by_role("button", name="Registrar movimentação", exact=True).click()
                expect(dialog).not_to_be_visible()
                assert stock(origin) == 12
                print("Browser: inventory entry passed.", flush=True)

                navigate("pedidos")
                page.get_by_role("button", name="+ Nova requisição", exact=True).click()
                dialog.get_by_label("Loja que fornecerá os materiais").select_option(str(origin))
                dialog.get_by_label("Loja que receberá os materiais").select_option(str(destination))
                dialog.get_by_label("Produto do item").select_option("990001")
                dialog.get_by_label("Quantidade solicitada").fill("4")
                dialog.get_by_role("button", name="Enviar requisição", exact=True).click()
                expect(dialog).not_to_be_visible()
                page.get_by_role("button", name="Ver detalhes", exact=True).click()
                dialog.get_by_role("button", name="Aprovar requisição", exact=True).click()
                expect(dialog).not_to_be_visible()
                page.get_by_role("button", name="Ver detalhes", exact=True).click()
                dialog.get_by_role("button", name="Atender e transferir estoque", exact=True).click()
                expect(dialog).not_to_be_visible()
                assert stock(origin) == 8
                assert stock(destination) == 4
                print("Browser: requisition approval and fulfillment passed.", flush=True)

                navigate("contagem")
                page.get_by_role("button", name="+ Nova contagem", exact=True).click()
                dialog.get_by_label("Loja inventariada").select_option(str(destination))
                dialog.get_by_label("Motivo / identificação da contagem").fill("Contagem no navegador")
                dialog.get_by_label("Produto do item").select_option("990001")
                dialog.get_by_label("Quantidade contada", exact=True).fill("3")
                dialog.get_by_role("button", name="Confirmar contagem e ajustar saldos", exact=True).click()
                expect(dialog).not_to_be_visible()
                assert stock(destination) == 3
                print("Browser: physical count adjustment passed.", flush=True)

                navigate('fornecedores')
                page.get_by_role('button', name='+ Novo fornecedor', exact=True).click()
                dialog.get_by_label('Nome fantasia').fill('Fornecedor do navegador')
                dialog.get_by_role('button',name='Salvar registro',exact=True).click()
                expect(dialog).not_to_be_visible()
                navigate('cotacoes')
                page.get_by_role('button',name='+ Nova cotação',exact=True).click()
                dialog.get_by_label('Título da cotação').fill('Compra do navegador')
                dialog.locator('[data-quote-product]').select_option('990001')
                dialog.locator('[data-quote-quantity]').fill('2')
                dialog.locator('[name="quote_supplier"]').check()
                dialog.get_by_role('button',name='Criar cotação',exact=True).click()
                expect(dialog).not_to_be_visible()
                page.get_by_role('button',name='Comparar ofertas',exact=True).click()
                portal_url=dialog.locator('[id^="quote-link-"]').input_value()
                supplier_page=context.new_page()
                supplier_page.on('pageerror',lambda error: errors.append(str(error)))
                supplier_page.goto(portal_url)
                expect(supplier_page.locator('#proposal-form')).to_be_visible()
                supplier_page.locator('#price-0').fill('9,8765')
                supplier_page.get_by_role('button',name='Enviar proposta',exact=True).click()
                expect(supplier_page.locator('#success-title')).to_be_visible()
                supplier_page.close()
                dialog.get_by_role('button',name='Fechar',exact=True).click()
                page.get_by_role('button',name='Comparar ofertas',exact=True).click()
                expect(dialog).to_contain_text('9,8765')
                dialog.get_by_role('button',name='Encerrar e escolher vencedores',exact=True).click()
                dialog.get_by_role('button',name='Confirmar ação',exact=True).click()
                expect(dialog).not_to_be_visible()
                page.get_by_role('button',name='Comparar ofertas',exact=True).click()
                dialog.get_by_role('button',name='Gerar ordens de compra',exact=True).click()
                dialog.get_by_label('Loja que receberá os materiais').select_option(str(origin))
                dialog.get_by_role('button',name='Gerar ordens de compra',exact=True).click()
                expect(dialog).not_to_be_visible()
                page.wait_for_function("() => window.App.view === 'compras' && !document.getElementById('app-content').hasAttribute('aria-busy')")
                page.locator('[data-action="view-purchase"]').click()
                dialog.get_by_role('button',name='Confirmar recebimento',exact=True).click()
                dialog.get_by_role('button',name='Confirmar ação',exact=True).click()
                expect(dialog).not_to_be_visible()
                assert stock(origin)==10
                expect(page.locator('#app-content')).to_contain_text('Recebida')
                print('Browser: quotation, supplier portal, purchase generation and receipt passed.',flush=True)
                page.get_by_role('button',name='Minha senha',exact=True).click()
                dialog.get_by_label('Senha atual',exact=False).fill('NavegadorSeguro2026!')
                dialog.locator('[name="new_password"]').fill('NovaSenhaNavegador2026!')
                dialog.locator('[name="confirm_password"]').fill('NovaSenhaNavegador2026!')
                dialog.get_by_role('button',name='Alterar senha',exact=True).click()
                expect(dialog).not_to_be_visible()
                print('Browser: self-service password change passed.',flush=True)

                for view in ("dashboard", "estoque", "pedidos", "contagem", "cotacoes",
                             "compras", "produtos", "fornecedores", "cadastros", "usuarios", "relatorios"):
                    navigate(view)
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), view

                page.evaluate("location.hash = 'dashboard'")
                expect(page.locator("#app-content h1")).to_be_visible()
                page.locator("#toast-region").evaluate("element => element.replaceChildren()")
                page.screenshot(path="/tmp/erp-ui-desktop.png", full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                expect(page.locator("#menu-toggle")).to_be_visible()
                page.locator("#menu-toggle").click()
                assert page.locator("body").evaluate("element => element.classList.contains('sidebar-open')")
                page.locator('[data-view="estoque"]').click()
                expect(page.locator("#app-content h1")).to_be_visible()
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "mobile overflow"
                page.wait_for_function("() => !document.body.classList.contains('sidebar-open') && document.getElementById('sidebar').getBoundingClientRect().right <= 0")
                assert page.locator(".data-table .cell-title").first.evaluate("element => parseFloat(getComputedStyle(element).fontSize)")>=16
                assert page.locator(".field-control").first.evaluate("element => parseFloat(getComputedStyle(element).fontSize)")>=16
                page.screenshot(path="/tmp/erp-ui-mobile.png", full_page=True)
                page.set_viewport_size({"width": 1440, "height": 1000})
                page.locator("#logout").click()
                page.wait_for_url("**/login.html")
                page.get_by_label("Usuário", exact=True).fill("admin_browser")
                page.get_by_label("Senha", exact=True).fill("NovaSenhaNavegador2026!")
                page.get_by_role("button", name="Entrar na plataforma").click()
                expect(page.locator("#app-content h1")).to_be_visible()
                assert not errors, errors
                browser.close()
                print("Browser smoke passed: bootstrap, catalogs, stock, requisition, count, supplier quote, purchase receipt, password, all views, mobile and logout/login.")
                print("Screenshots: /tmp/erp-ui-desktop.png and /tmp/erp-ui-mobile.png")
        finally:
            server.shutdown()
            thread.join(timeout=5)


if __name__ == "__main__":
    run()
