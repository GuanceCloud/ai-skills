"""These host-boundary checks also run in native Windows CI."""
import contextlib
import io
import unittest
from unittest import mock

from test_validate_contract import RESOLVER as R


class HostSupportTests(unittest.TestCase):
    def test_native_windows_cli_rejects_before_network_or_code(self):
        argv = ['resolve_rum_application.py', '--dataway-url', 'https://cn3-openway.guance.com',
                '--app-id', 'synthetic-app', '--temporary-auth-code-stdin',
                '--client-token-sink', '.env.local', '--state-file', '.rum/state.json',
                '--repository', '.', '--plan-digest', 'sha256:' + '0' * 64]
        with mock.patch.object(R.sys, 'platform', 'win32'), mock.patch.object(R.sys, 'argv', argv), \
                mock.patch.object(R, 'resolve_site') as network, \
                mock.patch.object(R, 'read_temporary_authorization_code') as code, \
                contextlib.redirect_stderr(io.StringIO()) as error:
            self.assertEqual(1, R.main())
        self.assertIn('WSL', error.getvalue())
        network.assert_not_called()
        code.assert_not_called()

    def test_unavailable_permission_api_has_actionable_error(self):
        with mock.patch.object(R.sys, 'platform', 'linux'), \
                mock.patch.object(R.os, 'fchmod', None, create=True):
            with self.assertRaisesRegex(R.ResolutionError, 'POSIX'):
                R.require_secure_storage()

    def test_windows_site_only_remains_credential_free(self):
        site = R.Site('guance', 'cn3', 'https://urls.guance.com/',
                      'https://cn3-openway.guance.com', 'https://cn3-ai-api.guance.com')
        argv = ['resolve_rum_application.py', '--dataway-url', site.dataway_url, '--site-only']
        with mock.patch.object(R.sys, 'platform', 'win32'), mock.patch.object(R.sys, 'argv', argv), \
                mock.patch.object(R, 'resolve_site', return_value=site), \
                mock.patch.object(R, 'read_temporary_authorization_code') as code, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, R.main())
        code.assert_not_called()


if __name__ == '__main__':
    unittest.main()
