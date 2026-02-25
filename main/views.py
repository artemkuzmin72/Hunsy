from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login

def index(request):
    return render(request, 'index.html')

@login_required
def main(request):
    return render(request, 'main.html')

def register(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("main")
    else:
        form = UserCreationForm()

    for field in form.fields.values():
        field.widget.attrs["class"] = "form-control"

    return render(request, "register.html", {"form": form})