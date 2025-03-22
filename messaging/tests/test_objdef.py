from django.test import TestCase

from dacite import from_dict

from messaging.objdef import DirectMessageContent, load_direct_message_content

class MessagingObjdefTestCase(TestCase):

    def test_direct_message_content(self):
        text_content_dict = {
            "type": "text",
            "text": "Hello, World!"
        }

        text_content = load_direct_message_content(text_content_dict)

        self.assertIsInstance(text_content, DirectMessageContent)
        self.assertEqual(text_content.type, "text")
        self.assertEqual(text_content.text, "Hello, World!")

        attachment_content_dict = {
            "type": "attachment",
            "attachment_type": "image",
            "attachment_id": "1234-1234-1234"
        }

        attachment_content = load_direct_message_content(attachment_content_dict)

        self.assertIsInstance(attachment_content, DirectMessageContent)
        self.assertEqual(attachment_content.type, "attachment")
        self.assertEqual(attachment_content.attachment_type, "image")
        self.assertEqual(attachment_content.attachment_id, "1234-1234-1234")


        attachment_content_dict = {
            "type": "test",
            "attachment_id": "1234-1234-1234"
        }

        with self.assertRaises(ValueError):
            load_direct_message_content(attachment_content_dict)
