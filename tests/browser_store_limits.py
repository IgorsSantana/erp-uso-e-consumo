"""Exercise the real seeded limits in the browser using a disposable database."""
import os
from pathlib import Path
import sys
import tempfile
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app import create_app
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server
from tests.browser_smoke import QuietHandler


def run():
    with tempfile.TemporaryDirectory(prefix='erp-browser-seed-') as directory:
        app = create_app({'TESTING': True, 'SEED_CATALOG': True,
                          'DATABASE': str(Path(directory)/'erp.sqlite3'), 'SECRET_KEY': 'browser-limits-test-only'})
        server = make_server('127.0.0.1', 0, app, threaded=True, request_handler=QuietHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path=os.environ.get('CHROMIUM_EXECUTABLE', '/usr/bin/chromium'),
                                                     headless=True, args=['--no-sandbox'])
                context = browser.new_context(viewport={'width': 1440, 'height': 1000}, locale='pt-BR')
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                response = context.request.post(base+'/api/setup', data={'nome': 'Gestão de limites', 'username': 'admin_limites', 'password': 'SenhaNavegador2026!'})
                assert response.ok, response.text()
                page.goto(base)
                page.locator('[data-view="produtos"]').first.click()
                page.locator('[data-action="stock-limits"][data-produto="369842"]').click()
                dialog = page.locator('#app-dialog')
                expect(dialog.get_by_label('Mínimo em BCS', exact=True)).to_have_value('20')
                expect(dialog.get_by_label('Máximo em BCS', exact=True)).to_have_value('40')
                expect(dialog.get_by_label('Mínimo em SJN', exact=True)).to_have_value('10')
                expect(dialog.get_by_label('Máximo em SJN', exact=True)).to_have_value('20')
                expect(dialog.get_by_label('Mínimo em MEP', exact=True)).to_have_value('')
                expect(dialog.get_by_label('Mínimo em MEP', exact=True)).to_be_disabled()
                dialog.get_by_label('Usar limites em MEP', exact=True).check()
                expect(dialog.get_by_label('Mínimo em MEP', exact=True)).to_have_value('0')
                dialog.get_by_label('Mínimo em MEP', exact=True).fill('4')
                dialog.get_by_label('Máximo em MEP', exact=True).fill('8')
                dialog.get_by_role('button', name='Salvar limites das lojas', exact=True).click()
                expect(dialog).not_to_be_visible()
                pairs = {row['loja_nome']: row for row in context.request.get(base+'/api/produtos/369842/limites').json()['lojas']}
                assert (pairs['BCS']['estoque_minimo'], pairs['SJN']['estoque_minimo'], pairs['MEP']['estoque_minimo']) == (20, 10, 4)
                page.locator('[data-action="stock-limits"][data-produto="337086"]').click()
                expect(dialog.get_by_label('Mínimo em BCS', exact=True)).to_have_value('1')
                expect(dialog.get_by_label('Máximo em BCS', exact=True)).to_have_value('2')
                expect(dialog.get_by_label('Máximo em SJN', exact=True)).to_be_disabled()
                # Close through the real modal button, then check max-only data.
                dialog.get_by_role('button', name='Cancelar', exact=True).click()
                page.locator('[data-action="stock-limits"][data-produto="367054"]').click()
                expect(dialog.get_by_label('Mínimo em BCS', exact=True)).to_have_value('0')
                expect(dialog.get_by_label('Máximo em BCS', exact=True)).to_have_value('7')
                expect(dialog.get_by_label('Máximo em SJN', exact=True)).to_have_value('2')
                page.screenshot(path='/tmp/erp-seeded-limits.png', full_page=False)
                assert not errors, errors
                browser.close()
                print('Browser: seeded store limits, missing values, independent edit, bakery BCS and max-only values passed.', flush=True)
        finally:
            server.shutdown()
            thread.join(timeout=5)


if __name__ == '__main__':
    run()
