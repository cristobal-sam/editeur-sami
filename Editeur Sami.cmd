@echo off
rem Double-clic : lance l'editeur (et le relance s'il s'arrete). Fermer la fenetre pour l'arreter.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0editeur.ps1"
