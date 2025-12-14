# accounts/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from .serializers import RegisterSerializer
from .models import InvitationCode

from game.models import Character, PlayerState  # <- PlayerState para mandar a 0-0 si quieres asegurar
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required


class RegisterView(APIView):
    """
    API para registro via JSON (la que ya tenías).
    /api/accounts/register/
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {"detail": "Cuenta creada", "username": user.username},
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@login_required
def logout_view(request):
    """
    Cierra la sesión del usuario y lo manda al menú de inicio.
    """
    logout(request)
    return redirect("start_menu")


def _get_character_and_lives_context(user):
    """
    Devuelve:
      character | None,
      lives (int|None),
      seconds_to_next_life (int|None),
      no_lives (bool)
    """
    character = Character.objects.filter(owner=user).first()
    if not character:
        return None, None, None, False

    # regen (cada 10 min según tu implementación)
    info = character.regen_lives(timezone.now())  # o character.regen_lives() si no recibe now
    lives = getattr(character, "lives", None)

    seconds_to_next = None
    if isinstance(info, dict):
        seconds_to_next = info.get("seconds_to_next")

    no_lives = bool(lives is not None and lives <= 0)
    return character, lives, seconds_to_next, no_lives


def start_menu(request):
    """
    Menú de inicio:
    - Si NO está logueado: muestra formulario de login y de registro (con código).
    - Si está logueado:
        - Si ya tiene personaje → botón "Entrar al mundo" (bloqueado si no hay vidas).
        - Si no tiene personaje → botón "Crear personaje".
    """

    # =========================
    # AUTENTICADO
    # =========================
    if request.user.is_authenticated:
        character, lives, seconds_to_next, no_lives = _get_character_and_lives_context(request.user)

        has_character = character is not None

        # (Opcional) si no tiene vidas, puedes asegurar que quede en 0-0
        # para que siempre reaparezca en zona segura incluso si se quedó en otra zona.
        if has_character and no_lives:
            state, _ = PlayerState.objects.get_or_create(
                character=character,
                defaults={"x": 9, "y": 9, "zone": "0-0"},
            )
            if state.zone != "0-0":
                state.zone = "0-0"
                state.x = 9
                state.y = 9
                state.save(update_fields=["zone", "x", "y"])

        return render(
            request,
            "start_menu.html",
            {
                "user_is_authenticated": True,
                "has_character": has_character,
                "lives": lives,
                "seconds_to_next_life": seconds_to_next or 0,
                "no_lives": no_lives,
            },
        )

    # =========================
    # NO AUTENTICADO
    # =========================
    form_type = request.POST.get("form_type")
    register_errors = {}

    if request.method == "POST" and form_type == "login":
        login_form = AuthenticationForm(request, data=request.POST)
    else:
        login_form = AuthenticationForm(request)

    if request.method == "POST":
        # -----------------
        # LOGIN
        # -----------------
        if form_type == "login":
            if login_form.is_valid():
                user = login_form.get_user()
                login(request, user)

                # 🔥 OJO: ya NO redirigimos directo a world si tiene personaje,
                # porque si tiene 0 vidas debe quedarse en el start_menu con el timer.
                return redirect("start_menu")
            else:
                messages.error(request, "Usuario o contraseña incorrectos.")

        # -----------------
        # REGISTRO
        # -----------------
        elif form_type == "register":
            username = request.POST.get("username", "").strip()
            password1 = request.POST.get("password1", "")
            password2 = request.POST.get("password2", "")
            invitation_code = request.POST.get("invitation_code", "").strip().upper()

            if not username:
                register_errors["username"] = "Ingresa un nombre de usuario."
            elif User.objects.filter(username=username).exists():
                register_errors["username"] = "Ese nombre de usuario ya está en uso."

            if not password1 or not password2:
                register_errors["password"] = "Debes escribir la contraseña dos veces."
            elif password1 != password2:
                register_errors["password"] = "Las contraseñas no coinciden."

            if not invitation_code:
                register_errors["invitation_code"] = "Debes ingresar un código de invitación."

            code_obj = None
            if not register_errors:
                try:
                    code_obj = InvitationCode.objects.get(code=invitation_code)
                except InvitationCode.DoesNotExist:
                    register_errors["invitation_code"] = "Código de invitación inválido."
                else:
                    if not code_obj.can_be_used():
                        register_errors["invitation_code"] = "Código agotado o inactivo."

            if not register_errors:
                user = User.objects.create_user(username=username, password=password1)
                code_obj.register_use()
                login(request, user)
                return redirect("create_character_form")

    return render(
        request,
        "start_menu.html",
        {
            "user_is_authenticated": False,
            "login_form": login_form,
            "register_errors": register_errors,
        },
    )
