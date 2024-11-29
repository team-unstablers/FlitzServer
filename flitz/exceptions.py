from rest_framework import exceptions

class UnsupportedOperationException(exceptions.APIException):
    status_code = 400
    default_detail = 'This operation is not supported. This incident has been reported.'
    default_code = 'unsupported_operation'