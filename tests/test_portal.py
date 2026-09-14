import importlib
import os
import tempfile
import unittest


class PortalAppTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ['PORTAL_DB'] = os.path.join(self.tempdir.name, 'portal_test.db')
        import portal_app
        importlib.reload(portal_app)
        portal_app.app.config['TESTING'] = True
        self.client = portal_app.app.test_client()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_register_login_and_download(self):
        payload = {
            'full_name': 'Mario Rossi',
            'email': 'mario@example.com',
            'password': 'secret123',
            'country': 'Italia',
            'account_type': 'utente'
        }

        register_response = self.client.post('/api/register', json=payload)
        self.assertEqual(register_response.status_code, 201)

        login_response = self.client.post('/api/login', json={
            'email': 'mario@example.com',
            'password': 'secret123'
        })
        self.assertEqual(login_response.status_code, 200)
        self.assertIn('session', login_response.get_json())

        download_response = self.client.get('/download/UniversalEmulatorbyDB.py')
        self.assertEqual(download_response.status_code, 200)
        self.assertIn(b'UniversalEmulator', download_response.data)


if __name__ == '__main__':
    unittest.main()
