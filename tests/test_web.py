"""Regression checks; all mutable data is mocked, no real students are touched."""
import copy
import gzip
import http.client
import threading
import time
import unittest
from io import BytesIO
from unittest.mock import patch, MagicMock
from http.server import ThreadingHTTPServer
import app


class QuietHandler(app.AuraHandler):
    def log_message(self, *args):
        pass
    def record_public_visit(self, *args):
        return []


class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), QuietHandler)
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join()

    def request(self, path, headers=None, method='GET', body=None):
        conn = http.client.HTTPConnection(*self.server.server_address)
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return result

    def test_anonymous_portal_never_loads_student_data(self):
        with patch.object(app, 'load_applications', side_effect=AssertionError('Unnecessary read')):
            status, _, body = self.request('/portal')
        self.assertEqual(status, 200)
        self.assertIn(b'action="/login"', body)
        self.assertNotIn(b'{{', body)

    def test_home_has_no_auth_or_event_dependency(self):
        def load(path, default):
            self.assertIn(path, (app.VIDEOS_PATH, app.CONTENT_PATH))
            return copy.deepcopy(default)
        with patch.object(app, 'load_json', side_effect=load):
            status, _, body = self.request('/')
        self.assertEqual(status, 200)
        self.assertNotIn(b'{{', body)
        self.assertNotIn(b'gratuito', body)
        self.assertIn(b'landing.js', body)
        self.assertNotIn(b'/script.js', body)

    def test_old_neon_promotion_is_migrated_without_writing(self):
        old = copy.deepcopy(app.LEGACY_PUBLIC_CONTENT)
        with patch.object(app, 'save_json', side_effect=AssertionError('Unexpected write')):
            result = app.normalize_content(old)
        self.assertEqual(result['hero'], app.DEFAULT_CONTENT['hero'])
        self.assertEqual(result['stats'], app.DEFAULT_CONTENT['stats'])
        old['hero']['title'] = 'Mi titular personalizado'
        self.assertEqual(app.normalize_content(old)['hero']['title'], 'Mi titular personalizado')

    def test_html_compression_and_opt_out(self):
        status, headers, body = self.request('/portal', {'Accept-Encoding':'gzip'})
        self.assertEqual(status, 200)
        self.assertEqual(headers['Content-Encoding'], 'gzip')
        self.assertIn(b'action="/login"', gzip.decompress(body))
        _, headers, _ = self.request('/portal', {'Accept-Encoding':'gzip;q=0'})
        self.assertNotIn('Content-Encoding', headers)

    def test_video_ranges_and_head(self):
        path = '/FOTOS/dominadas.mp4'
        original = (app.BASE_DIR / path.lstrip('/')).read_bytes()
        for spec, expected in [('bytes=0-99', original[:100]), ('bytes=-77', original[-77:]), ('bytes=100-', original[100:])]:
            with self.subTest(spec=spec):
                status, headers, body = self.request(path, {'Range':spec})
                self.assertEqual(status, 206)
                self.assertEqual(body, expected)
                self.assertEqual(int(headers['Content-Length']),len(expected))
        status, _, body = self.request(path, {'Range':f'bytes={len(original)}-'})
        self.assertEqual(status,416)
        self.assertEqual(body,b'')
        status, headers, body = self.request(path, {'Range':'bytes=0-99'},method='HEAD')
        self.assertEqual(status,206)
        self.assertEqual(body,b'')
        self.assertEqual(headers['Content-Length'],'100')

    def test_expired_session_is_rejected_without_sync_write(self):
        with patch.object(app,'load_json',return_value={'expired':{'user':'demo','role':'user','expires':time.time()-1}}), patch.object(app,'save_json') as save:
            self.assertIsNone(app.get_session_user('aura_user_session=expired', app.USER_SESSION_COOKIE,'user'))
            save.assert_not_called()

    def test_db_connection_reused_only_within_request(self):
        connection=MagicMock(closed=False)
        with patch.object(app,'open_db_connection',return_value=connection) as connect:
            app.DB_REQUEST.active=True
            app.DB_REQUEST.connection=None
            try:
                with app.db_connect() as a:
                    pass
                with app.db_connect() as b:
                    pass
                self.assertIs(a,b)
                connect.assert_called_once()
                connection.close.assert_not_called()
            finally:
                app.DB_REQUEST.active=False
                app.DB_REQUEST.connection=None
            with app.db_connect():
                pass
            self.assertEqual(connect.call_count,2)
            connection.close.assert_called_once()

    def test_apply_saves_before_queueing_email(self):
        events=[]
        smtp={'enabled':True}
        with patch.object(app,'load_applications',return_value=[]), patch.object(app,'save_json',side_effect=lambda *args: events.append('saved')), patch.object(app,'load_smtp_settings',return_value=smtp), patch.object(app,'smtp_missing_fields',return_value=[]), patch.object(app,'run_background_job',side_effect=lambda *args,**kwargs: events.append('queued')), patch.object(app,'notify_application',side_effect=AssertionError('Blocking mail')):
            status, headers, _ = self.request('/apply', {'Content-Type':'application/x-www-form-urlencoded'}, 'POST', 'username=demo&password=test-only&email=demo%40example.com&skill=Pino&goal=Equilibrio')
        self.assertEqual(events,['saved','queued'])
        self.assertEqual(status,303)
        self.assertEqual(headers['Location'],'/?status=ok#registro')

    def test_day_and_chat_updates_save_and_redirect(self):
        applications=[{'username':'demo','approved':True,'plan':app.copy_default_plan()}]
        with patch.object(app,'get_session_user',return_value='demo'), patch.object(app,'load_applications',return_value=applications), patch.object(app,'save_json') as save:
            status, headers, _ = self.request('/portal/day/update', {'Content-Type':'application/x-www-form-urlencoded'}, 'POST', 'week=1&day=1&status=done&feedback=Bien')
            self.assertEqual(status,303)
            self.assertEqual(applications[0]['plan']['weeks'][0]['days'][0]['status'],'done')
            save.assert_called_once()
        with patch.object(app,'get_session_user',return_value='demo'), patch.object(app,'load_json',return_value=[]), patch.object(app,'save_json') as save:
            status, _, _ = self.request('/portal/chat/send', {'Content-Type':'application/x-www-form-urlencoded'}, 'POST', 'text=Mensaje+de+prueba')
            self.assertEqual(status,303)
            self.assertEqual(save.call_args.args[1][0]['text'],'Mensaje de prueba')


    def test_daily_carousel_preserves_exercise_save_addresses(self):
        from html.parser import HTMLParser
        class Forms(HTMLParser):
            def __init__(self):
                super().__init__()
                self.current = None
                self.items = []
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == 'form' and 'data-portal-item-form' in attrs:
                    self.current = {}
                if tag == 'input' and self.current is not None and attrs.get('type') == 'hidden':
                    self.current[attrs['name']] = attrs['value']
            def handle_endtag(self, tag):
                if tag == 'form' and self.current is not None:
                    self.items.append(self.current)
                    self.current = None
        plan = app.copy_default_plan()
        plan['weeks'][0]['days'][0]['items'] = [
            {'exercise':'Dominadas'},
            {'type':'superset','name':'Superserie A','exercises':[{'exercise':'Fondos'},{'exercise':'Remo'}]},
            {'exercise':'Plancha'},
        ]
        plan['weeks'][0]['days'][1]['items'] = [{'exercise':'Sentadillas'}]
        plan['weeks'][0]['days'][2]['rest'] = True
        rendered = app.render_training_plan(plan)
        forms = Forms()
        forms.feed(rendered)
        self.assertEqual([(f['week'],f['day'],f['item'],f.get('sub_item')) for f in forms.items], [
            ('1','1','1',None),('1','1','2','1'),('1','1','2','2'),('1','1','3',None),('1','2','1',None)
        ])
        self.assertEqual(rendered.count('data-day-exercises'), 2)
        self.assertEqual(rendered.count('Superserie A'), 2)
        self.assertIn('Descanso o movilidad.', rendered)
        self.assertIn('Generar PDF semanal', rendered)
        self.assertNotIn('⏳', rendered)

    def test_weekly_pdf_contains_complete_training_feedback(self):
        plan = app.copy_default_plan()
        week = plan['weeks'][0]
        week['title'] = 'Semana de control'
        week['summary'] = 'Resumen final del alumno'
        week['days'][0] = {
            'title': 'Tirón y técnica',
            'rest': False,
            'status': '',
            'status_note': 'Molestia leve al final',
            'feedback': 'Buena energía durante la sesión',
            'items': [
                {
                    'exercise': 'Dominadas lastradas', 'sets': '4', 'reps': '5',
                    'weight': '8 kg', 'rest': '120 s', 'notes': 'Subida explosiva',
                    'status': 'done', 'status_note': '', 'student_note': 'Carga 8 kg estable',
                },
                {
                    'type': 'superset', 'name': 'Superserie final', 'rounds': '3',
                    'rest_between': '90 s', 'exercises': [
                        {
                            'exercise': 'Remo australiano', 'sets': '', 'reps': '12',
                            'weight': '', 'rest': '', 'notes': '', 'status': 'missed',
                            'status_note': 'Falla tecnica en la ultima ronda',
                            'student_note': 'Antebrazos cargados',
                        },
                        {
                            'exercise': 'Curl en barra', 'sets': '', 'reps': '10',
                            'weight': '', 'rest': '', 'notes': '', 'status': '',
                            'status_note': '', 'student_note': '',
                        },
                    ],
                },
            ],
        }
        application = {
            'username': 'alumno_demo', 'name': 'Alumno Demo', 'skill': 'Dominadas',
            'goal': 'Mejorar fuerza', 'plan': plan,
        }
        payload = app.build_week_report_pdf(application, 1)
        self.assertTrue(payload.startswith(b'%PDF'))
        reader = app.PdfReader(BytesIO(payload))
        text = '\n'.join(page.extract_text() or '' for page in reader.pages)
        normalized_text = ' '.join(text.split())
        for expected in [
            'Informe semanal de entrenamiento', 'Alumno Demo', 'Dominadas lastradas',
            'Carga 8 kg estable', 'Falla tecnica', 'Superserie final', 'Pendiente',
            'Buena energía', 'Molestia leve', 'Resumen final del alumno',
        ]:
            self.assertIn(expected, normalized_text)

    def test_authenticated_portal_keeps_plan_and_chat(self):
        application={'username':'demo','approved':True,'skill':'Pino','goal':'Equilibrio','plan':app.copy_default_plan()}
        with patch.object(app,'get_session_user',return_value='demo'), patch.object(app,'load_applications',return_value=[application]), patch.object(app,'load_chat_messages',return_value=[]):
            body=app.render_portal_page({},'test')
        self.assertNotIn('{{',body)
        self.assertIn('portal-active-view',body)
        self.assertIn('Plan activo',body)
        self.assertIn('/portal/chat/send',body)
        self.assertIn('/logout',body)


if __name__ == '__main__':
    unittest.main()
