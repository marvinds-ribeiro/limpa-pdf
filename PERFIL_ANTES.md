# Perfil de desempenho — `Apagou demais ORIGINAL.pdf`

**Páginas:** 81 · **Tamanho:** 8.5 MB · **Tempo total do pipeline:** 435.2 s (7.3 min)

## Tempo por etapa

| etapa | tempo total (s) | s/página | % do total |
| --- | ---: | ---: | ---: |
| limpa_pdf | 40.3 | 0.50 | 9.3% |
| embutir_ocr | 260.9 | 3.22 | 59.9% |
| numerar_paginas | 7.1 | 0.09 | 1.6% |
| dividir_pdf | 0.0 | 0.00 | 0.0% |
| exportar_md | 126.9 | 1.57 | 29.1% |

## Hotspots (cProfile) — embutir_ocr

| função | tempo cumulativo (s) | tempo próprio (s) | chamadas |
| --- | ---: | ---: | ---: |
| `image_to_data` (pytesseract.py) | 222.1 | 0.0 | 81 |
| `_elementos` (limpa_pdf_mpsc.py) | 16.2 | 0.0 | 81 |
| `_iter_elementos` (limpa_pdf_mpsc.py) | 16.2 | 13.0 | 81 |
| `render` (page.py) | 5.7 | 4.0 | 81 |
| `save` (pytesseract.py) | 5.5 | 0.0 | 162 |
| `_preparar_imagem_ocr` (limpa_pdf_mpsc.py) | 5.4 | 0.1 | 81 |
| `save` (Image.py) | 4.9 | 0.0 | 81 |
| `_save` (PngImagePlugin.py) | 4.8 | 0.0 | 81 |
| `_save` (ImageFile.py) | 4.8 | 0.0 | 81 |
| `parse_content_stream` (_content_stream.py) | 2.9 | 2.9 | 162 |
| `to_pil` (bitmap.py) | 2.1 | 0.0 | 81 |
| `<bilateralFilter>` (~) | 1.6 | 1.6 | 81 |
| `<threshold>` (~) | 1.0 | 1.0 | 81 |
| `<built-in method _io.open>` (~) | 0.1 | 0.1 | 495 |
| `save` (_methods.py) | 0.0 | 0.0 | 1 |
| `opener` (tempfile.py) | 0.0 | 0.0 | 82 |
| `<built-in method nt.open>` (~) | 0.0 | 0.0 | 84 |
| `open` (_methods.py) | 0.0 | 0.0 | 1 |
| `<built-in method _io.open_code>` (~) | 0.0 | 0.0 | 63 |
| `get_textpage` (page.py) | 0.0 | 0.0 | 81 |
| `_escala_render` (limpa_pdf_mpsc.py) | 0.0 | 0.0 | 81 |
| `open` (_local.py) | 0.0 | 0.0 | 2 |
| `_open_pdf` (document.py) | 0.0 | 0.0 | 1 |
| `<built-in method msvcrt.open_osfhandle>` (~) | 0.0 | 0.0 | 244 |
| `_release_save` (threading.py) | 0.0 | 0.0 | 243 |

## Hotspots (cProfile) — exportar_md

| função | tempo cumulativo (s) | tempo próprio (s) | chamadas |
| --- | ---: | ---: | ---: |
| `_tabelas_md` (limpa_pdf_mpsc.py) | 126.2 | 0.0 | 1 |
| `extract_tables` (page.py) | 125.7 | 0.0 | 81 |
| `find_tables` (page.py) | 125.3 | 0.0 | 81 |
| `render_contents` (pdfinterp.py) | 109.3 | 0.0 | 81 |
| `render_string` (pdfdevice.py) | 2.0 | 0.0 | 16578 |
| `render_string_horizontal` (pdfdevice.py) | 1.9 | 0.1 | 16578 |
| `render_char` (page.py) | 1.8 | 0.1 | 83819 |
| `render_char` (converter.py) | 1.6 | 0.2 | 83819 |
| `_extrair_paginas` (limpa_pdf_mpsc.py) | 0.5 | 0.0 | 1 |
| `open` (pdf.py) | 0.1 | 0.0 | 1 |
| `<built-in method _io.open_code>` (~) | 0.1 | 0.1 | 201 |
| `get_textpage` (page.py) | 0.1 | 0.0 | 81 |
| `_open_pdf` (document.py) | 0.0 | 0.0 | 1 |
| `render_image` (page.py) | 0.0 | 0.0 | 101 |
| `_parse_wopen` (psparser.py) | 0.0 | 0.0 | 871 |
| `render_image` (converter.py) | 0.0 | 0.0 | 101 |
| `__get_openssl_constructor` (hashlib.py) | 0.0 | 0.0 | 14 |
| `<built-in method _io.open>` (~) | 0.0 | 0.0 | 4 |
| `open` (_local.py) | 0.0 | 0.0 | 2 |
| `<built-in method _hashlib.openssl_md5>` (~) | 0.0 | 0.0 | 1 |
| `opengroup` (_parser.py) | 0.0 | 0.0 | 22 |
| `<built-in method _hashlib.openssl_sha3_224>` (~) | 0.0 | 0.0 | 1 |
| `<built-in method _hashlib.openssl_sha1>` (~) | 0.0 | 0.0 | 1 |
| `<built-in method _hashlib.openssl_sha256>` (~) | 0.0 | 0.0 | 1 |
| `<built-in method _hashlib.openssl_sha512>` (~) | 0.0 | 0.0 | 1 |

