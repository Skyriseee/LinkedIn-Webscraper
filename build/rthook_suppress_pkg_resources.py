"""PyInstaller-Runtime-Hook (siehe LinkedInScraper.spec: Analysis(runtime_hooks=[...])).

Custom Runtime-Hooks laufen VOR den automatisch erkannten Paket-Runtime-Hooks (siehe
PyInstaller/depend/analysis.py:analyze_runtime_hooks - eigene Hooks werden zuerst an
priority_scripts angehängt). Genau das brauchen wir hier: einer der automatischen
Hooks (pyi_rth_pkgres, ausgelöst durch ein Paket im Abhängigkeitsbaum, das noch das
alte pkg_resources-Namespace-Package-Schema benutzt) importiert pkg_resources, und
dessen eigenes __init__.py meldet dabei seine Deprecation - harmlos (keine
Funktionsänderung), aber unschöne Konsolenausgabe bei jedem Start der exe. Ursache ist
der Build-Workaround `setuptools<81` (siehe build/requirements-build.txt, CHANGELOG
0.7.6 - neuere Setuptools haben pkg_resources entfernt, das PyInstallers eigenes
modulegraph aber noch braucht). Ein Filter in run.py selbst kommt zu spät, weil der
auslösende Import schon vorher passiert.
"""
import warnings

warnings.filterwarnings("ignore", message=r"pkg_resources is deprecated.*")
