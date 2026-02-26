from rest_framework import permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authtoken.serializers import AuthTokenSerializer

# from knox.models import AuthToken


class LoginAPI(APIView):
    permission_classes = (permissions.AllowAny,)

    # def post(self, request, format=None):
    #     serializer = AuthTokenSerializer(data=request.data)
    #     serializer.is_valid(raise_exception=True)
    #
    #     user = serializer.validated_data["user"]
    #     token_instance = AuthToken.objects.create(user)
    #
    #     return Response(
    #         {
    #             "user": {"id": user.id, "username": user.username, "email": user.email},
    #             "token": token_instance[1],  # This is the token string
    #             "expiry": token_instance[0].expiry,
    #         }
    #     )
