import os
import tempfile
import unittest

import httpx
import main


class AsyncMultipartSupportTests(unittest.TestCase):
    def test_local_reference_is_materialized_as_bytes(self):
        handle, path = tempfile.mkstemp(suffix=".png")
        try:
            os.write(handle, b"reference-image-bytes")
            filename, content, content_type = main.async_multipart_file(path)

            self.assertEqual(os.path.basename(path), filename)
            self.assertEqual(b"reference-image-bytes", content)
            self.assertEqual("image/png", content_type)
            self.assertIsInstance(content, bytes)
        finally:
            os.close(handle)
            os.unlink(path)

    def test_multipart_form_uses_async_compatible_stream(self):
        client = httpx.AsyncClient()
        request = client.build_request(
            "POST",
            "https://example.invalid/v1/videos",
            data=main.async_multipart_form_data({"model": "gpt-image-2", "prompt": "test"}),
            files=[("images", ("reference.png", b"image-bytes", "image/png"))],
        )

        self.assertIsInstance(request.stream, httpx.AsyncByteStream)


if __name__ == "__main__":
    unittest.main()
