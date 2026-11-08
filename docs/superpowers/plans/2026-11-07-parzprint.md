# Parzprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** App de captura de tela para Windows e Linux, estilo Lightshot, com anotações e um botão Texto que extrai o texto da imagem com o Indra, local e offline.

**Architecture:** Um processo Python com PySide6. A bandeja mantém o app vivo; o atalho global (pynput) ou o comando `parzprint --capture` (via instância única com QLocalServer) dispara a captura. A captura fotografa os monitores com mss e abre um overlay por monitor com seleção, editor de anotações e barras. O OCR é um adaptador `OcrEngine` que devolve `TextBlock`s; a interface do painel de texto só conhece `TextBlock`. Lógica sem Qt (anotações, settings, autostart, hotkey, ocr) é testada com pytest; a interface é verificada rodando o app.

**Tech Stack:** Python 3.11+, PySide6, indra-ocr, mss, pynput, platformdirs, Pillow, pytest, PyInstaller.

**Spec:** `docs/superpowers/specs/2026-11-07-parzprint-design.md`

## Global Constraints

- Python 3.11 ou mais novo. Pacote `parzprint/`, testes em `tests/`.
- Nenhuma chamada de rede exceto o download do modelo do Indra, feito pela própria biblioteca na primeira execução do OCR.
- Textos da interface em português do Brasil.
- Atalho padrão `Ctrl+Shift+S`. Nome de arquivo padrão `Parzprint_AAAA-MM-DD_HH-MM-SS`. Formato padrão PNG. Pasta padrão: pasta Imagens do usuário.
- Config em `platformdirs.user_config_dir("Parzprint")` no Windows e `user_config_dir("parzprint")` no Linux, arquivo `settings.json`.
- Cor padrão de anotação: vermelho `#E53935`. Paleta fixa: `#E53935`, `#FDD835`, `#43A047`, `#1E88E5`, `#000000`, `#FFFFFF`.
- Commits em português, mensagem curta no imperativo, com a linha `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Módulos de interface (`overlay`, `toolbar`, `textpanel`, `tray`, `settings_window`) importam de modelos (`annotations`, `settings`, `ocr`), nunca o inverso.

## Review Focus

1. Dois monitores com escalas diferentes (125% e 100%): a seleção deve recortar a região certa da foto do monitor onde o mouse está, sem deslocamento. Teste em Task 7 (`test_monitor_for_point`, `test_crop_uses_monitor_offset`).
2. Seleção arrastada de baixo para cima ou da direita para a esquerda deve gerar o mesmo retângulo que a direção oposta. Teste em Task 8 (`test_normalize_rect`).
3. Blocos de OCR do Indra em coordenadas da imagem completa quando a imagem passada é só a seleção: adaptador deve devolver coordenadas relativas à imagem passada. Teste em Task 4 (`test_indra_blocks_relative_to_image`).
4. `settings.json` com atalho inválido (`"Ctrl+"`) deve voltar ao padrão sem travar o app. Teste em Task 2 (`test_invalid_hotkey_falls_back_to_default`).
5. Texto da ferramenta Texto confirmado vazio não deve criar anotação. Teste em Task 3 (`test_empty_text_annotation_is_dropped`).

---

### Task 0: Verificar Indra neste Windows (spike, descartável)

**Files:**
- Create: `spike/indra_check.py` (apagado ao final da task)

**Interfaces:**
- Produces: decisão registrada em `docs/superpowers/specs/2026-11-07-parzprint-design.md` seção 11 (Indra funciona no Windows: sim ou não, e tempo por imagem).

- [ ] **Step 1: Criar ambiente virtual e instalar o Indra**

Run (na pasta do projeto):
```bash
python -m venv .venv && .venv/Scripts/pip install indra-ocr pillow
```
Expected: instalação termina sem erro. Se falhar por falta de wheel do ONNX Runtime no Windows, anotar o erro.

- [ ] **Step 2: Gerar uma imagem de teste em português**

Em `spike/indra_check.py`, com Pillow, desenhar em fundo branco 800×200 o texto `Ação rápida: João comprou 3 pães às 10h.` em fonte do sistema tamanho 32, salvar em `spike/sample.png`.

- [ ] **Step 3: Rodar o Indra sobre a imagem e medir o tempo**

No mesmo script, carregar o modelo via API Python do indra-ocr (ver README do pacote: `from indra import ...`), reconhecer `spike/sample.png`, imprimir o texto, os blocos com coordenadas e o tempo em segundos.

Run: `.venv/Scripts/python spike/indra_check.py`
Expected: imprime texto contendo `João` e `pães` com acentos corretos e tempo abaixo de 5 s.

- [ ] **Step 4: Registrar o resultado**

Na seção 11 da especificação, acrescentar uma linha "Verificado em 2026-11-07: Indra <funciona | não funciona> no Windows, X s por imagem, acentos <ok | com erros>" e o nome exato da classe e método da API usados (eles serão usados na Task 4). Se não funcionar, parar e decidir com o usuário o motor substituto antes da Task 4.

- [ ] **Step 5: Apagar o spike e commitar**

```bash
rm -rf spike && git add -A && git commit -m "Registra verificação do Indra no Windows"
```

---

### Task 1: Esqueleto do projeto

**Files:**
- Create: `pyproject.toml`, `parzprint/__init__.py`, `tests/__init__.py`, `.gitignore`, `README.md`

**Interfaces:**
- Produces: pacote `parzprint` instalável em modo editável; `pytest` roda da raiz.

- [ ] **Step 1: Escrever `pyproject.toml`**

Build backend `setuptools`. Nome `parzprint`, versão `0.1.0`, `requires-python = ">=3.11"`. Dependências: `PySide6`, `mss`, `pynput`, `platformdirs`, `Pillow`, `indra-ocr`. Grupo opcional `dev`: `pytest`, `pyinstaller`. Script de console `parzprint = "parzprint.__main__:main"`.

- [ ] **Step 2: `.gitignore`** com `.venv/`, `__pycache__/`, `dist/`, `build/`, `*.spec`, `.pytest_cache/`.

- [ ] **Step 3: `README.md`** com nome, uma frase do objetivo e os comandos de instalar (`pip install -e .[dev]`), rodar (`python -m parzprint`) e testar (`pytest`).

- [ ] **Step 4: Instalar e rodar pytest vazio**

Run: `.venv/Scripts/pip install -e .[dev] && .venv/Scripts/pytest`
Expected: `no tests ran`, exit code 5, sem erro de import.

- [ ] **Step 5: Commit** `git add -A && git commit -m "Cria esqueleto do projeto Parzprint"`

---

### Task 2: Configurações

**Files:**
- Create: `parzprint/settings.py`, `tests/test_settings.py`

**Interfaces:**
- Produces:
  - `@dataclass Settings(hotkey: str = "Ctrl+Shift+S", autostart: bool = True, save_dir: str = <pasta Imagens>, image_format: str = "PNG", ocr_engine: str = "indra")`
  - `DEFAULT_PICTURES_DIR() -> str` (usa `platformdirs.user_pictures_dir()`)
  - `settings_path() -> Path` (config dir via platformdirs + `settings.json`)
  - `load_settings(path: Path | None = None) -> Settings`
  - `save_settings(settings: Settings, path: Path | None = None) -> None`
  - `is_valid_hotkey(text: str) -> bool` (formato `Mod+Mod+Key`, mods em `Ctrl, Shift, Alt, Win`, pelo menos um mod e exatamente uma tecla final não vazia)

- [ ] **Step 1: Escrever testes**

```python
def test_defaults(): s = Settings(); assert s.hotkey == "Ctrl+Shift+S" and s.image_format == "PNG" and s.autostart is True
def test_roundtrip(tmp_path): p = tmp_path/"s.json"; save_settings(Settings(hotkey="Alt+P", image_format="JPG"), p); assert load_settings(p) == Settings(hotkey="Alt+P", image_format="JPG")
def test_missing_file_returns_defaults(tmp_path): assert load_settings(tmp_path/"nope.json") == Settings()
def test_corrupt_file_returns_defaults_and_rewrites(tmp_path): p = tmp_path/"s.json"; p.write_text("{oops"); assert load_settings(p) == Settings(); assert json.loads(p.read_text())["hotkey"] == "Ctrl+Shift+S"
def test_invalid_hotkey_falls_back_to_default(tmp_path): p = tmp_path/"s.json"; p.write_text(json.dumps({"hotkey": "Ctrl+"})); assert load_settings(p).hotkey == "Ctrl+Shift+S"
def test_unknown_format_falls_back_to_png(tmp_path): ... image_format "GIF" -> "PNG"
def test_is_valid_hotkey(): assert is_valid_hotkey("Ctrl+Shift+S"); assert not is_valid_hotkey("S"); assert not is_valid_hotkey("Ctrl+"); assert not is_valid_hotkey("")
```

- [ ] **Step 2: Rodar** `pytest tests/test_settings.py -v`. Expected: FAIL (import).
- [ ] **Step 3: Implementar `parzprint/settings.py`** com as assinaturas acima. Campos desconhecidos no JSON são ignorados; campos inválidos voltam ao padrão individualmente.
- [ ] **Step 4: Rodar**. Expected: todos PASS.
- [ ] **Step 5: Commit** `git commit -m "Adiciona leitura e escrita das configurações"`

---

### Task 3: Modelo de anotações

**Files:**
- Create: `parzprint/annotations.py`, `tests/test_annotations.py`

**Interfaces:**
- Produces:
  - `@dataclass Point(x: float, y: float)`
  - Dataclasses `Pencil(points: list[Point], color: str, width: int = 3)`, `Line(start: Point, end: Point, color: str, width: int = 3)`, `Arrow(start, end, color, width=3)`, `Rect(start, end, color, width=3)`, `Marker(points: list[Point], color: str, width: int = 18)` (alpha 40%), `Text(position: Point, text: str, color: str, size: int = 18)`
  - `Annotation = Pencil | Line | Arrow | Rect | Marker | Text`
  - `class AnnotationStack`: `add(a: Annotation) -> None` (ignora `Text` com `text.strip() == ""`), `undo() -> Annotation | None`, `items() -> list[Annotation]`, `__len__`
  - `render(image: PIL.Image.Image, items: list[Annotation]) -> PIL.Image.Image` (não altera a original; desenha com `PIL.ImageDraw`; seta com ponta triangular de 12 px)
  - `PALETTE = ["#E53935", "#FDD835", "#43A047", "#1E88E5", "#000000", "#FFFFFF"]`, `DEFAULT_COLOR = PALETTE[0]`

- [ ] **Step 1: Escrever testes**

```python
def test_add_and_undo(): s = AnnotationStack(); s.add(Line(Point(0,0), Point(5,5), "#E53935")); assert len(s) == 1; assert isinstance(s.undo(), Line); assert len(s) == 0; assert s.undo() is None
def test_empty_text_annotation_is_dropped(): s = AnnotationStack(); s.add(Text(Point(1,1), "   ", "#000000")); assert len(s) == 0
def test_render_rect_paints_border_pixel(): img = Image.new("RGB", (50,50), "white"); out = render(img, [Rect(Point(10,10), Point(30,30), "#E53935", width=1)]); assert out.getpixel((10,20)) == (229,57,53); assert out.getpixel((20,20)) == (255,255,255); assert img.getpixel((10,20)) == (255,255,255)
def test_render_arrow_paints_head(): out = render(Image.new("RGB",(60,20),"white"), [Arrow(Point(5,10), Point(50,10), "#000000")]); assert out.getpixel((48,10)) == (0,0,0)
def test_render_marker_is_translucent(): out = render(Image.new("RGB",(40,40),"white"), [Marker([Point(5,20), Point(35,20)], "#FDD835")]); r,g,b = out.getpixel((20,20)); assert (r,g,b) != (255,255,255) and (r,g,b) != (253,216,53)
```

- [ ] **Step 2: Rodar**. Expected: FAIL.
- [ ] **Step 3: Implementar `parzprint/annotations.py`**. Para `Marker`, desenhar em camada RGBA e compor com `Image.alpha_composite`. Para `Text`, usar `ImageFont.load_default(size)` quando fonte do sistema não for encontrada.
- [ ] **Step 4: Rodar**. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "Adiciona modelo e renderização das anotações"`

---

### Task 4: OCR: interface, motor falso e adaptador do Indra

**Files:**
- Create: `parzprint/ocr/__init__.py`, `parzprint/ocr/base.py`, `parzprint/ocr/fake.py`, `parzprint/ocr/indra.py`, `tests/test_ocr.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) TextBlock(text: str, x: int, y: int, width: int, height: int)`
  - `class OcrEngine(Protocol)`: `name: str`; `recognize(image: PIL.Image.Image) -> list[TextBlock]`
  - `class OcrError(Exception)`
  - `reading_order(blocks: list[TextBlock]) -> list[TextBlock]` (agrupa em linhas quando os centros verticais distam menos que metade da altura média; ordena linhas por `y`, dentro da linha por `x`)
  - `join_text(blocks: list[TextBlock]) -> str` (um bloco por linha, `\n` entre eles, já em ordem de leitura)
  - `class FakeEngine(blocks: list[TextBlock])` implementa `OcrEngine` devolvendo os blocos dados
  - `class IndraEngine` implementa `OcrEngine`; carrega o modelo na primeira chamada (lazy); converte o resultado do Indra (API registrada na Task 0) para `TextBlock` com coordenadas inteiras relativas à imagem passada; qualquer exceção da biblioteca vira `OcrError(str(e))`
  - `get_engine(name: str) -> OcrEngine` em `ocr/__init__.py` (`"indra"` → `IndraEngine()`; desconhecido → `OcrError`)

- [ ] **Step 1: Escrever testes**

```python
def test_reading_order_sorts_lines_then_columns():
    b = [TextBlock("c",0,40,10,10), TextBlock("b",50,0,10,10), TextBlock("a",0,2,10,10)]
    assert [t.text for t in reading_order(b)] == ["a","b","c"]
def test_join_text(): assert join_text([TextBlock("olá",0,0,1,1), TextBlock("mundo",0,20,1,1)]) == "olá\nmundo"
def test_fake_engine_returns_given_blocks(): ...
def test_get_engine_unknown_raises(): with pytest.raises(OcrError): get_engine("x")
def test_indra_blocks_relative_to_image():
    # monkeypatch IndraEngine._run_model para devolver um resultado no formato do Indra com um bloco em bbox [10,20,110,60]
    # assert recognize(Image.new("RGB",(200,100))) == [TextBlock("abc",10,20,100,40)]
def test_indra_wraps_library_errors(monkeypatch): # _run_model levanta RuntimeError -> OcrError
```

- [ ] **Step 2: Rodar**. Expected: FAIL.
- [ ] **Step 3: Implementar.** Em `IndraEngine`, isolar a chamada à biblioteca em `_run_model(self, image) -> Any` e a conversão em `_to_blocks(self, raw) -> list[TextBlock]`, para que os testes substituam `_run_model`. Usar a classe/método exatos anotados na Task 0.
- [ ] **Step 4: Rodar**. Expected: PASS.
- [ ] **Step 5: Verificação manual**: `python -c "from PIL import Image; from parzprint.ocr import get_engine; print(get_engine('indra').recognize(Image.open('<um print seu>')))"`. Expected: lista de `TextBlock` com texto legível.
- [ ] **Step 6: Commit** `git commit -m "Adiciona interface de OCR e adaptador do Indra"`

---

### Task 5: Autostart

**Files:**
- Create: `parzprint/autostart.py`, `tests/test_autostart.py`

**Interfaces:**
- Produces:
  - `executable_command() -> str` (congelado pelo PyInstaller: `sys.executable`; senão `"<sys.executable>" -m parzprint`)
  - `desktop_entry(command: str) -> str` (conteúdo `.desktop`: `[Desktop Entry]`, `Type=Application`, `Name=Parzprint`, `Exec=<command>`, `X-GNOME-Autostart-enabled=true`)
  - `linux_autostart_path() -> Path` (`~/.config/autostart/parzprint.desktop`)
  - `set_autostart(enabled: bool, *, platform: str = sys.platform, command: str | None = None, linux_path: Path | None = None) -> None`
  - `is_autostart_enabled(*, platform: str = sys.platform, linux_path: Path | None = None) -> bool`
  - Windows: chave `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, valor `Parzprint`, via `winreg`; constante `WINDOWS_RUN_KEY` e função interna `_windows_key_path()` sobrescrevível em teste.

- [ ] **Step 1: Escrever testes**

```python
def test_desktop_entry_contains_exec(): e = desktop_entry("/opt/parzprint"); assert "Exec=/opt/parzprint" in e and "Name=Parzprint" in e and e.startswith("[Desktop Entry]")
def test_linux_enable_disable(tmp_path): p = tmp_path/"a.desktop"; set_autostart(True, platform="linux", command="x", linux_path=p); assert p.exists() and is_autostart_enabled(platform="linux", linux_path=p); set_autostart(False, platform="linux", linux_path=p); assert not p.exists()
@pytest.mark.skipif(sys.platform != "win32", reason="windows") def test_windows_enable_disable(monkeypatch): monkeypatch.setattr(autostart, "_windows_key_path", lambda: r"Software\ParzprintTest\Run"); set_autostart(True, platform="win32", command="C:\\x.exe"); assert is_autostart_enabled(platform="win32"); set_autostart(False, platform="win32"); assert not is_autostart_enabled(platform="win32")
```

- [ ] **Step 2: Rodar**. FAIL. **Step 3: Implementar.** **Step 4: Rodar**. PASS.
- [ ] **Step 5: Commit** `git commit -m "Adiciona início automático no Windows e Linux"`

---

### Task 6: Atalho global

**Files:**
- Create: `parzprint/hotkey.py`, `tests/test_hotkey.py`

**Interfaces:**
- Consumes: `is_valid_hotkey` (Task 2).
- Produces:
  - `to_pynput(hotkey: str) -> str` (`"Ctrl+Shift+S"` → `"<ctrl>+<shift>+s"`; `Win` → `<cmd>`; teclas especiais `F1..F12`, `Print` → `<f1>`, `<print_screen>`)
  - `from_qt_key_event(modifiers: set[str], key: str) -> str | None` (monta `"Ctrl+Shift+S"` a partir de nomes já extraídos; `None` se nenhum modificador ou tecla for só modificador)
  - `is_wayland(env: Mapping[str, str] = os.environ) -> bool` (`XDG_SESSION_TYPE == "wayland"` ou `WAYLAND_DISPLAY` definido, só quando `sys.platform` começa com `linux`)
  - `class GlobalHotkey`: `__init__(hotkey: str, callback: Callable[[], None])`, `start() -> None` (pynput `GlobalHotKeys` em thread), `stop() -> None`, `rebind(hotkey: str) -> None`. Erro de registro vira `HotkeyError`.

- [ ] **Step 1: Testes**

```python
def test_to_pynput(): assert to_pynput("Ctrl+Shift+S") == "<ctrl>+<shift>+s"; assert to_pynput("Win+Print") == "<cmd>+<print_screen>"; assert to_pynput("Alt+F2") == "<alt>+<f2>"
def test_from_qt_key_event(): assert from_qt_key_event({"Ctrl","Shift"}, "S") == "Ctrl+Shift+S"; assert from_qt_key_event(set(), "S") is None; assert from_qt_key_event({"Ctrl"}, "Ctrl") is None
def test_is_wayland(monkeypatch): monkeypatch.setattr(sys, "platform", "linux"); assert is_wayland({"XDG_SESSION_TYPE": "wayland"}); assert not is_wayland({"XDG_SESSION_TYPE": "x11"}); monkeypatch.setattr(sys, "platform", "win32"); assert not is_wayland({"XDG_SESSION_TYPE": "wayland"})
```

- [ ] **Step 2: Rodar**. FAIL. **Step 3: Implementar.** **Step 4: Rodar**. PASS.
- [ ] **Step 5: Commit** `git commit -m "Adiciona registro do atalho global"`

---

### Task 7: Captura de tela

**Files:**
- Create: `parzprint/capture.py`, `tests/test_capture.py`

**Interfaces:**
- Produces:
  - `@dataclass Monitor(index: int, x: int, y: int, width: int, height: int, image: PIL.Image.Image)`
  - `grab_all() -> list[Monitor]` (mss; ignora o monitor 0 "virtual" do mss)
  - `monitor_for_point(monitors: list[Monitor], x: int, y: int) -> Monitor | None`
  - `crop(monitor: Monitor, x: int, y: int, w: int, h: int) -> PIL.Image.Image` (coordenadas globais → locais subtraindo `monitor.x/y`)
  - `class CaptureError(Exception)` (falha do mss, por exemplo Wayland sem suporte)

- [ ] **Step 1: Testes** (sem tela: constroem `Monitor` com imagens Pillow)

```python
def test_monitor_for_point(): m = [Monitor(1,0,0,100,100,img), Monitor(2,100,0,100,100,img)]; assert monitor_for_point(m,150,50).index == 2; assert monitor_for_point(m,500,50) is None
def test_crop_uses_monitor_offset(): img = Image.new("RGB",(100,100),"white"); img.putpixel((10,10),(1,2,3)); m = Monitor(2,100,0,100,100,img); out = crop(m,110,10,5,5); assert out.size == (5,5) and out.getpixel((0,0)) == (1,2,3)
```

- [ ] **Step 2: Rodar**. FAIL. **Step 3: Implementar.** **Step 4: Rodar**. PASS.
- [ ] **Step 5: Verificação manual**: `python -c "from parzprint.capture import grab_all; [m.image.save(f'mon{m.index}.png') for m in grab_all()]"`. Expected: um PNG por monitor com o conteúdo da tela. Apagar os PNGs.
- [ ] **Step 6: Commit** `git commit -m "Adiciona captura dos monitores"`

---

### Task 8: Overlay de seleção

**Files:**
- Create: `parzprint/geometry.py`, `parzprint/overlay.py`, `tests/test_geometry.py`

**Interfaces:**
- Consumes: `Monitor`, `grab_all`, `crop` (Task 7).
- Produces:
  - `geometry.normalize_rect(x1, y1, x2, y2) -> tuple[int,int,int,int]` (x, y, w, h com w,h ≥ 0)
  - `geometry.place_toolbars(sel: QRect, screen: QRect, side_size: QSize, bottom_size: QSize) -> tuple[QPoint, QPoint]` (lateral à direita da seleção, inferior abaixo; se não couber, esquerda / acima; se ainda não couber, dentro da seleção)
  - `class SelectionOverlay(QWidget)` por monitor: janela sem borda, sempre no topo, cobrindo o monitor, mostra a foto escurecida a 50%; arrastar desenha a seleção clara com rótulo `L × A`; alças de 8 px nos cantos e bordas para ajustar; `Esc` cancela. Sinal `selected(QRect)` em coordenadas globais, sinal `cancelled()`.
  - `class CaptureSession(QObject)`: `start()` chama `grab_all`, cria um `SelectionOverlay` por monitor, conecta sinais; ao `selected`, fecha os outros overlays e emite `region_ready(monitor: Monitor, rect: QRect)`; ao `cancelled`, fecha tudo. Erro de captura emite `failed(str)`.

- [ ] **Step 1: Testes de geometria**

```python
def test_normalize_rect(): assert normalize_rect(50,50,10,10) == (10,10,40,40); assert normalize_rect(10,10,50,50) == (10,10,40,40)
def test_place_toolbars_prefers_right_and_below(): ...assert side.x() == sel.right()+6 and bottom.y() == sel.bottom()+6
def test_place_toolbars_flips_when_near_edge(): ...seleção colada à direita e embaixo da tela → side à esquerda, bottom acima
```

- [ ] **Step 2: Rodar**. FAIL. **Step 3: Implementar `geometry.py`.** **Step 4: Rodar**. PASS.
- [ ] **Step 5: Implementar `overlay.py`** (sem testes automáticos). Pintura em `paintEvent`: foto, retângulo escuro com buraco na seleção, borda tracejada, rótulo de tamanho, alças.
- [ ] **Step 6: Verificação manual**: script temporário que cria `QApplication`, `CaptureSession().start()` e imprime o `rect` recebido. Arrastar em cada direção, ajustar pela alça, `Esc`. Expected: retângulo impresso bate com a área, `Esc` fecha tudo, funciona no segundo monitor.
- [ ] **Step 7: Commit** `git commit -m "Adiciona overlay de seleção de área"`

---

### Task 9: Editor: barras e ferramentas de anotação

**Files:**
- Create: `parzprint/toolbar.py`, `parzprint/editor.py`
- Modify: `parzprint/overlay.py` (após `selected`, o overlay do monitor escolhido entra em modo edição em vez de fechar)

**Interfaces:**
- Consumes: `AnnotationStack`, dataclasses de anotação, `render`, `PALETTE`, `DEFAULT_COLOR` (Task 3); `place_toolbars` (Task 8).
- Produces:
  - `class Tool(Enum)`: `PENCIL, LINE, ARROW, RECT, MARKER, TEXT`
  - `class SideToolbar(QWidget)`: botões por `Tool`, botão de cor (abre popup com `PALETTE` + "Mais cores…" via `QColorDialog`), botão desfazer. Sinais `tool_changed(Tool)`, `color_changed(str)`, `undo_requested()`. Tooltips em português: Lápis, Linha, Seta, Retângulo, Marca-texto, Texto, Cor, Desfazer.
  - `class BottomToolbar(QWidget)`: botões Salvar, Copiar, Imprimir, Texto, Fechar. Sinais `save_requested, copy_requested, print_requested, text_requested, close_requested`. Método `set_busy(busy: bool, label: str = "")` mostra indicador de carregando no botão Texto.
  - `class Editor(QObject)`: recebe o overlay, `Monitor`, `QRect`; mantém `AnnotationStack`, ferramenta e cor atuais; trata mouse do overlay dentro da seleção criando anotações em coordenadas relativas à seleção; `Text` abre um `QLineEdit` flutuante na posição, confirma com Enter ou perda de foco; `set_tools_enabled(bool)`; `composite() -> PIL.Image.Image` (recorte + `render`); atalhos `Ctrl+Z`.

- [ ] **Step 1: Implementar `toolbar.py`.** Ícones: `QStyle.StandardPixmap` onde existir, senão texto curto; tamanho 28 px por botão, fundo escuro semitransparente, borda arredondada.
- [ ] **Step 2: Implementar `editor.py` e ligar no overlay.** O overlay, após `selected`, para de redimensionar por arraste fora das alças e delega mouse ao `Editor`; `paintEvent` desenha `render` das anotações sobre a seleção (converter PIL → `QImage` via `ImageQt`).
- [ ] **Step 3: Verificação manual**: cada ferramenta produz a forma esperada; mudar cor afeta só as próximas; desfazer remove a última; texto vazio não cria nada; `Esc` fecha; as barras ficam à direita/abaixo e invertem perto da borda.
- [ ] **Step 4: Commit** `git commit -m "Adiciona barras e ferramentas de anotação"`

---

### Task 10: Exportar: salvar, copiar, imprimir

**Files:**
- Create: `parzprint/export.py`, `tests/test_export.py`
- Modify: `parzprint/editor.py` (conecta sinais da `BottomToolbar`)

**Interfaces:**
- Consumes: `Settings` (Task 2), `Editor.composite()` (Task 9).
- Produces:
  - `default_filename(now: datetime, image_format: str) -> str` → `Parzprint_2026-11-07_19-53-02.png` (`.jpg` para JPG)
  - `save_image(image: PIL.Image.Image, path: Path, image_format: str) -> None` (JPG converte para RGB, qualidade 92)
  - `copy_image(image: PIL.Image.Image) -> None` (`QApplication.clipboard().setImage`)
  - `print_image(image: PIL.Image.Image, parent: QWidget) -> None` (`QPrintDialog`, ajusta ao papel mantendo proporção)
  - `ask_save_path(parent, settings: Settings, now: datetime) -> Path | None` (`QFileDialog.getSaveFileName` iniciando em `settings.save_dir / default_filename`)

- [ ] **Step 1: Testes**

```python
def test_default_filename(): assert default_filename(datetime(2026,11,7,19,53,2), "PNG") == "Parzprint_2026-11-07_19-53-02.png"; assert default_filename(..., "JPG").endswith(".jpg")
def test_save_png_and_jpg(tmp_path): img = Image.new("RGBA",(4,4),(255,0,0,255)); save_image(img, tmp_path/"a.png","PNG"); save_image(img, tmp_path/"a.jpg","JPG"); assert Image.open(tmp_path/"a.png").size == (4,4); assert Image.open(tmp_path/"a.jpg").mode == "RGB"
```

- [ ] **Step 2: Rodar**. FAIL. **Step 3: Implementar.** **Step 4: Rodar**. PASS.
- [ ] **Step 5: Ligar no editor**: Salvar → `ask_save_path` + `save_image` + fechar (erro de escrita → `QMessageBox.critical` e permanece); Copiar e `Enter` → `copy_image` + fechar; `Ctrl+S` → salvar; Imprimir → `print_image`, não fecha; Fechar → fecha.
- [ ] **Step 6: Verificação manual**: salvar PNG e JPG, copiar e colar no Paint, imprimir em "Microsoft Print to PDF", pasta sem permissão mostra erro e mantém a captura.
- [ ] **Step 7: Commit** `git commit -m "Adiciona salvar, copiar e imprimir a captura"`

---

### Task 11: Painel de texto (OCR)

**Files:**
- Create: `parzprint/ocr_worker.py`, `parzprint/textpanel.py`, `tests/test_textpanel_model.py`
- Modify: `parzprint/editor.py`, `parzprint/overlay.py`

**Interfaces:**
- Consumes: `OcrEngine`, `TextBlock`, `reading_order`, `join_text`, `OcrError`, `get_engine` (Task 4); `BottomToolbar.set_busy` (Task 9); `Editor.set_tools_enabled` (Task 9).
- Produces:
  - `class OcrWorker(QThread)`: `__init__(engine: OcrEngine, image: PIL.Image.Image)`; sinais `finished_ok(list)`, `failed(str)`, `progress(str)` (emite `"Baixando modelo…"` se o cache do modelo não existir antes da primeira chamada, senão `"Lendo texto…"`).
  - `class TextSelectionModel` (sem Qt, em `textpanel.py`): `__init__(blocks: list[TextBlock])` (já em ordem de leitura); `select_only(i: int)`, `select_range_by_drag(rect: tuple[int,int,int,int])` (seleciona blocos cujo retângulo intersecta), `clear()`, `selected_indices() -> list[int]`, `selected_text() -> str`, `all_text() -> str`, `hit(x: int, y: int) -> int | None`.
  - `class TextPanel(QWidget)`: `QPlainTextEdit` editável com `all_text`, botões Copiar tudo, Copiar seleção, Fechar painel; mensagem `Nenhum texto encontrado` quando a lista é vazia; estado de erro com a mensagem e botão Tentar de novo. Sinais `hover_block(int | None)`, `closed()`, `retry()`. Método `highlight_block(i: int | None)` destaca a linha `i`.
  - No `Editor`: `request_text()` roda o worker (uma vez por captura; resultado em `self._ocr_blocks`), `set_tools_enabled(False)` enquanto o painel está aberto, desenha caixas translúcidas por bloco sobre a imagem (azul `#1E88E5` 25%, selecionados 50%), hover sobre caixa ↔ `highlight_block`, arrastar seleciona via `select_range_by_drag`, clique via `select_only`. Painel à direita da seleção se couber, senão à esquerda (`place_toolbars` estendido ou função nova `place_panel`).

- [ ] **Step 1: Testes do modelo**

```python
B = [TextBlock("a",0,0,10,10), TextBlock("b",20,0,10,10), TextBlock("c",0,20,10,10)]
def test_hit(): m = TextSelectionModel(B); assert m.hit(5,5) == 0 and m.hit(25,5) == 1 and m.hit(50,50) is None
def test_select_only_and_text(): m = TextSelectionModel(B); m.select_only(1); assert m.selected_text() == "b"
def test_drag_selects_intersecting_in_reading_order(): m = TextSelectionModel(B); m.select_range_by_drag((5,5,30,20)); assert m.selected_indices() == [0,1,2] and m.selected_text() == "a\nb\nc"
def test_all_text(): assert TextSelectionModel(B).all_text() == "a\nb\nc"
```

- [ ] **Step 2: Rodar**. FAIL. **Step 3: Implementar `TextSelectionModel`.** **Step 4: Rodar**. PASS.
- [ ] **Step 5: Implementar `OcrWorker`, `TextPanel` e a integração no `Editor`/overlay.**
- [ ] **Step 6: Verificação manual**: botão Texto mostra carregando, painel abre com o texto; hover nos dois sentidos destaca; arrastar sobre a imagem seleciona e "Copiar seleção" copia só aquilo; "Copiar tudo" copia tudo; fechar painel reativa as ferramentas e as anotações seguem lá; reabrir não roda o OCR de novo; imagem sem texto mostra "Nenhum texto encontrado"; simular erro (engine `"x"` nas settings) mostra erro e Tentar de novo.
- [ ] **Step 7: Commit** `git commit -m "Adiciona painel de texto com OCR do Indra"`

---

### Task 12: Instância única, bandeja, janela de configurações e ponto de entrada

**Files:**
- Create: `parzprint/single_instance.py`, `parzprint/tray.py`, `parzprint/settings_window.py`, `parzprint/app.py`, `parzprint/__main__.py`, `assets/icon.png`, `tests/test_cli.py`

**Interfaces:**
- Consumes: tudo anterior.
- Produces:
  - `single_instance.SERVER_NAME = "parzprint-single-instance"`; `class SingleInstance(QObject)`: `try_acquire() -> bool` (cria `QLocalServer`; falso se já existe), `send(message: str) -> bool`, sinal `message_received(str)`.
  - `parse_args(argv: list[str]) -> str` → `"capture"`, `"settings"` ou `"none"` (`--capture`, `--settings`).
  - `class Tray(QSystemTrayIcon)`: menu Capturar, Configurações, Sair; duplo clique captura; `notify(title: str, text: str)`. Sinais `capture_requested, settings_requested, quit_requested`.
  - `class SettingsWindow(QDialog)`: campo de atalho (`HotkeyEdit(QLineEdit)` que grava a combinação via `from_qt_key_event`), checkbox Iniciar com o sistema, pasta padrão com botão Escolher…, formato PNG/JPG, motor de OCR (combo com "Indra"). Em Wayland, campo de atalho desativado e texto: `Em Wayland o atalho global não é suportado. Cadastre nas configurações de teclado do sistema o comando: parzprint --capture`. Botões Salvar e Cancelar. Sinal `saved(Settings)`.
  - `class App(QObject)`: liga tudo: carrega settings, `SingleInstance`, `Tray`, `GlobalHotkey` (exceto Wayland), `CaptureSession`; aplica `set_autostart` ao salvar settings; `rebind` do atalho ao salvar; erro de atalho em uso → `tray.notify`; `CaptureSession.failed` → `tray.notify`.
  - `main(argv=None) -> int` em `__main__.py`: se outra instância existe, `send(parse_args)` e retorna 0; senão sobe `App` e, se o argumento for `capture`/`settings`, executa após iniciar.

- [ ] **Step 1: Teste** `test_parse_args`: `parse_args(["--capture"]) == "capture"`, `["--settings"] == "settings"`, `[] == "none"`.
- [ ] **Step 2: Rodar**. FAIL. **Step 3: Implementar `parse_args` e os módulos.** **Step 4: Rodar**. PASS.
- [ ] **Step 5: Verificação manual**: `python -m parzprint` sobe só a bandeja; atalho padrão captura; segunda execução `python -m parzprint --capture` dispara captura na primeira e sai; mudar o atalho nas configurações passa a valer na hora; ligar Iniciar com o sistema cria a chave no registro (`reg query HKCU\Software\Microsoft\Windows\CurrentVersion\Run`); Sair encerra.
- [ ] **Step 6: Commit** `git commit -m "Adiciona bandeja, configurações e instância única"`

---

### Task 13: Empacotamento

**Files:**
- Create: `build.py`, seção "Gerar executável" no `README.md`

**Interfaces:**
- Produces: `dist/Parzprint/Parzprint.exe` (Windows) ou `dist/Parzprint/Parzprint` (Linux).

- [ ] **Step 1: Escrever `build.py`** que chama `PyInstaller.__main__.run` com: `--name Parzprint --windowed --onedir --icon assets/icon.ico --add-data assets;assets` (separador `:` no Linux), entrada `parzprint/__main__.py`, `--collect-all indra` (nome do pacote conforme Task 0) e `--collect-all onnxruntime`.
- [ ] **Step 2: Rodar** `python build.py`. Expected: termina sem erro e gera `dist/Parzprint/`.
- [ ] **Step 3: Verificação manual** do executável: abre na bandeja, captura, OCR funciona (primeira vez baixa o modelo), autostart aponta para o `.exe` (`executable_command()`), fechar e reabrir mantém configurações.
- [ ] **Step 4: README**: comandos de build e nota de que o Linux deve ser gerado numa máquina Linux.
- [ ] **Step 5: Commit** `git commit -m "Adiciona geração do executável com PyInstaller"`

---

## Checklist manual final (antes de considerar pronto)

- [ ] Captura com atalho e pelo menu da bandeja, em cada monitor.
- [ ] Cada ferramenta de anotação e desfazer.
- [ ] Salvar PNG, salvar JPG, copiar, imprimir, fechar, Esc, Enter.
- [ ] Texto: carregando, painel, hover nos dois sentidos, arrastar e copiar seleção, copiar tudo, sem texto, erro e tentar de novo, reabrir sem rodar de novo.
- [ ] Configurações: atalho novo vale na hora; autostart liga e desliga; pasta e formato respeitados.
- [ ] Segunda instância com `--capture` e `--settings`.
- [ ] No Linux (quando disponível): X11 com atalho; Wayland com aviso e `--capture`.
