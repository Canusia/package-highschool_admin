"""`class_number` is a CharField on ClassSection; Colleague/Ethos tenants store
codes like `BIOL-1408-CDU09`. Serializing it as an integer 500'd the HS admin
Registrations by Term table (package-highschool_admin#9).
"""
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from ..views.api.serializers import (
    HSAdminClassSectionSerializer, HSAdminRegClassSectionSerializer,
)


def _section(class_number):
    return SimpleNamespace(
        course=SimpleNamespace(name='BIOL 1408', title='Biology',
                               credit_hours=Decimal('4.00')),
        section_number='CDU09',
        class_number=class_number,
    )


class RegClassSectionClassNumberTests(SimpleTestCase):

    def test_non_numeric_class_number_serializes(self):
        data = HSAdminRegClassSectionSerializer(_section('BIOL-1408-CDU09')).data
        self.assertEqual(data['class_number'], 'BIOL-1408-CDU09')

    def test_numeric_class_number_serializes_as_string(self):
        data = HSAdminRegClassSectionSerializer(_section('12345')).data
        self.assertEqual(data['class_number'], '12345')

    def test_class_list_serializer_uses_model_charfield(self):
        field = HSAdminClassSectionSerializer().fields['class_number']
        self.assertEqual(type(field).__name__, 'CharField')
