from django.test import TestCase

from dacite import from_dict

from card.objdef import CardObject, TextElement, ImageElement


# Create your tests here.

class CardObjdefTestCase(TestCase):

    def test_card_objdef(self):
        card_obj_dict = {
            "schema_version": "v1.0-test",
            "background": None,
            "elements": [
                { "type": "text", "transform": { "position": { "x": 4.0, "y": 3.0 }, "scale": 1.0, "rotation": 1.0 }, "text": "Hello, World!" },
                { "type": "image", "transform": {"position": {"x": 4.0, "y": 3.0}, "scale": 1.0, "rotation": 1.0}, "source": { "id": "1234-1234-1234" }, "size": { "width": 100.0, "height": 100.0 } },
            ],

            "properties": {}
        }

        card_obj = from_dict(data_class=CardObject, data=card_obj_dict)

        self.assertIsInstance(card_obj, CardObject)
        self.assertEqual(card_obj.schema_version, "v1.0-test")

        self.assertIsInstance(card_obj.elements[0], TextElement)
        self.assertIsInstance(card_obj.elements[1], ImageElement)

