# Registro de cambios

Los cambios notables de py-foliation. Las versiones publicadas, con sus
ruedas, AppImages y RPM, están en
[Codeberg](https://codeberg.org/nivaca/py-foliation/releases) y
[GitHub](https://github.com/nivaca/py-foliation/releases).

## Sin publicar

- `tools/zenodo.py`: la descripción del depósito es ahora el README entero
  de la etiqueta, en HTML. El borrador recibe además el colaborador (el
  director del proyecto), los idiomas, el copyright, el repositorio en
  GitHub, el lenguaje de programación y el estado del desarrollo; estos
  últimos, por la API de registros de Zenodo, porque la de depósitos no los
  admite. El token puede guardarse en el llavero del escritorio
  (`secret-tool store --label="Zenodo token" service zenodo`) en vez de en
  `$ZENODO_TOKEN`; `tools/zenodo.py check-token` dice si hay uno.

- `tools/zenodo.py` prepara el depósito de una versión en Zenodo. `collect`
  deja en `dist/zenodo/` el árbol de la etiqueta como
  `py-foliation-VERSIÓN-source.tar.gz`, con su firma, un `SHA256SUMS` del
  depósito, firmado, y la clave pública, y comprueba cada firma con solo esa
  clave (`--packages` añade los archivos de la versión). `upload` lo sube a
  Zenodo como borrador, versión nueva del depósito si ya lo hay, y nunca lo
  publica. `tools/release.py` reúne ahora el depósito después de la etiqueta
  y lo sube como borrador, salvo con `--no-zenodo`. Los metadatos están en
  `.zenodo.json`.
- `tools/zenodo.py`: la descripción del depósito deja fuera la línea que
  lleva a los README en otras lenguas y la sección Screenshots, cuyas
  imágenes Zenodo no muestra.
- `tools/release.py` publica ahora cada versión en Zenodo
  (`tools/zenodo.py upload --publish`), en vez de dejar un borrador;
  `--zenodo-draft` todavía lo deja. `tools/zenodo.py publish` publica un
  borrador que ya está allí (por omisión, el que espera con el título del
  proyecto).
- `tools/test.py` corre las pruebas a la vez, cada archivo en un proceso
  de pytest propio, tantos como procesadores haya, primero los más lentos.
  `tools/release.py` y el `%check` del RPM las corren así, y no en un
  solo pytest.
- Aquí solo se guarda el RPM: `tools/release.py` hace y firma la rueda, el
  paquete fuente, la AppImage y `SHA256SUMS` en `build/release/` (no en
  `dist/`), y el depósito para Zenodo en `build/zenodo/`; los publica desde
  allí y al final borra ambas carpetas. `tools/bundle-appimage.py` escribe
  por omisión en `build/release/`; `dist/` solo tiene la copia del RPM que
  deja `packaging/build-rpm.sh`.

## 1.0.3 — 2026-11-22

- **Cada versión firmada**: además del RPM, cada archivo publicado (la
  rueda, el paquete fuente, la AppImage) va con su firma (`.asc`), con
  `SHA256SUMS` y su firma, y con la clave pública; también la etiqueta de
  la versión va firmada. `tools/release.py` hace siempre el RPM firmado
  (`--no-rpm` lo deja fuera) y comprueba cada firma con la clave publicada
  antes de publicar nada. Los README explican cómo comprobar una descarga.

## 1.0.2 — 2026-11-21

- `docs/TERCEROS_es.md` (y `docs/THIRD-PARTY.md`, en inglés) enumera el
  software libre que usa py-foliation, para funcionar y para construirlo,
  probarlo y empaquetarlo, con sus licencias; los README enlazan a él.

- Se necesita Python 3.14 o posterior (antes, 3.15): `requires-python`,
  los instaladores de `installers/` y los README. Las pruebas pasan con
  3.14; la AppImage sigue llevando Python 3.15.
- `installers/install.ps1` se detenía en Windows si no estaba instalado
  Python 3.17: el lanzador py escribe "No suitable Python runtime found"
  cuando le falta una versión, y PowerShell lo tomaba como un error que
  terminaba el instalador antes de que probara la versión siguiente. La
  prueba está ahora dentro de un try/catch.
- Un trabajo nuevo del flujo de trabajo instala py-foliation con
  `installers/` en Linux, macOS y Windows, ejecuta la orden y la
  desinstala. La instalación en macOS solo corre con las etiquetas de
  versión, los lunes y cuando se lanza a mano, porque GitHub a menudo no
  tiene un Mac libre.
- `docs/DESCRIPCIÓN_es.md` se ciñe a seis secciones, cada una de menos
  de 4000 caracteres, en tercera persona.

## 1.0.1 — 2026-11-19

- **Arrastrar miniaturas.** Lo que se soltaba entre dos miniaturas, o a
  la derecha de la última de una fila, iba al final del libro; ahora va
  junto a la más cercana. Las páginas van detrás de la miniatura que está
  bajo el puntero (la mitad izquierda de la primera las pone delante), y
  una línea del color de realce indica dónde. Al puntero solo lo sigue
  una nota pequeña ("3 páginas"). El movimiento espera a que termine el
  arrastre, de modo que la pregunta sobre las etiquetas no se abre en
  medio de él; lo mismo en la lista de páginas.
- **Instaladores para Python** en Linux, Windows y macOS:
  `installers/install.py` (solo con la biblioteca estándar) crea un
  entorno de Python propio, instala py-foliation con la ventana a partir
  de la rueda de la última versión publicada (en GitHub o, si no, en
  Codeberg), enlaza las órdenes en `~/.local/bin` o las añade al PATH en
  Windows, y añade la entrada del menú; `--version`, `--from`,
  `--no-gui`, `--no-menu` y `--uninstall`. `install.sh` e `install.ps1`
  buscan Python 3.15 o posterior y lo ejecutan, también como órdenes de
  una sola línea.

## 1.0 — 2026-11-19

- **Una ventana más ligera.** Las miniaturas las dibuja
  `QPdfPageRenderer`, de Qt, en un hilo propio, primero las visibles; los
  tamaños de página vienen de pikepdf, así que la ventana nunca espera a
  que PDFium los lea.
- Cada miniatura se guarda según lo que muestra (unos 256 MB en total),
  así que mover, borrar, duplicar, editar etiquetas y deshacer no obliga
  a redibujar ninguna.
- Las páginas elegidas se copian entre la lista y las miniaturas de una
  vez (200 páginas: de 2,9 s a 0,08 s), y `arrange.rebuild` solo cambia
  las páginas que cambian (borrar una página de 1000: de 0,3 s a
  0,04 s).
- La vista previa se vuelve a dibujar al editar una etiqueta solo cuando
  un encabezado, un pie o una marca de agua pendientes muestran
  etiquetas de página.

## 0.12.1 — 2026-11-18

- Las miniaturas vuelven a poder arrastrarse en su panel: Qt las movía
  por su cuenta y se quedaba con los arrastres antes de que pudieran
  mover las páginas. Un arrastre mueve las páginas elegidas, con Ctrl las
  copia, y los PDF que se sueltan insertan sus páginas.

## 0.12 — 2026-11-18

- Una barra en la parte superior del panel de miniaturas: girar a la
  izquierda y a la derecha, mover una página antes o después, duplicar,
  borrar, insertar una página en blanco o las páginas de un PDF, y un
  menú More (Más) con las demás operaciones del menú Pages (Páginas) (el
  menú del clic derecho también tiene More). Las acciones que no son
  posibles aparecen desactivadas.
- Teclas en las miniaturas y en la lista: Ctrl+R, Ctrl+Shift+R,
  Alt+flechas, Ctrl+D y Supr; las páginas movidas siguen elegidas.
- View > List of pages (Ver > Lista de páginas) oculta o muestra la
  lista, y esto se conserva de una sesión a otra.
- `packaging/build-rpm.sh` copia también el RPM más reciente en `dist/`,
  junto a la rueda, el paquete fuente y la AppImage.

## 0.11 — 2026-11-18

- **Un panel de miniaturas**: View > Thumbnails (Ver > Miniaturas, F4)
  muestra las páginas en un panel junto a la vista previa, que puede
  pasar a otro lado de la ventana o flotar. Un control deslizante, o Ctrl
  y la rueda del ratón, fijan su tamaño, de 48 a 400 píxeles. El panel y
  la lista comparten la página actual, las páginas elegidas, el menú, los
  arrastres y los PDF que se sueltan.
- La lista de páginas sigue siendo una lista; ya no se convierte en
  miniaturas.

## 0.10 — 2026-11-18

- **Ordenar páginas**: mover, borrar, duplicar, invertir, girar, insertar
  páginas en blanco o las de otro PDF, reemplazar, extraer y dividir
  (`arrange.py`). Las páginas duplicadas conservan sus anotaciones, y los
  enlaces a páginas borradas van a la página que las seguía. Las páginas
  en blanco toman las cajas y la rotación de la página anterior.
- Las etiquetas siguen a las páginas o se quedan en su posición; la
  página en que se abre el archivo sigue a su página.
- `py-foliation pages`: `--order`, `--move`, `--delete`, `--duplicate`,
  `--reverse`, `--rotate`, `--insert-blank`, `--insert`, `--replace`,
  `--extract`, `--split-every`, `--split-at` y `--labels
  follow|position`.
- En la ventana: arrastrar páginas en la lista (con Ctrl, copiarlas),
  soltar PDF para insertar sus páginas, un diálogo para cada operación en
  el menú Pages y en el menú de las páginas; todo se puede deshacer y se
  escribe con Save.

## 0.9 — 2026-11-17

- Salida en PDF/A y PDF/X, hecha por pdf2iso: File > Save as (Archivo >
  Guardar como), `--conform` y Pages > On several files (Páginas > En
  varios archivos).
- El correo de contacto es ahora nicolasvaughan@proton.me.

## 0.8 — 2026-11-17

- **Marcas de agua** (`watermark.py`, `py-foliation watermark`): un texto
  o una página de otro PDF, girados, escalados, con una opacidad, delante
  del contenido o detrás, visibles solo al imprimir o solo en la
  pantalla, que se pueden quitar y actualizar, con perfiles.
- **Varios encabezados y pies por página.** Lo que py-foliation añade a
  una página es ahora una pila de capas (`stamps.py`), y cualquier capa
  puede quitarse; los registros de la 0.7 se siguen leyendo. `--add`
  conserva los que ya están en las páginas, `--update` reemplaza el
  último añadido y `--remove-bates` quita solo los que llevan números
  Bates. `$date` tiene diez formatos (`--date-format`).
- **Lotes de archivos**: los números Bates continúan de un archivo al
  siguiente; `--output-dir`, `--name-prefix` y `--name-suffix` en todas
  las órdenes que escriben archivos; Pages > On several files en la
  ventana.

## 0.7.1 — 2026-11-17

- Los encabezados y pies funcionan con pikepdf 10.8, la versión de
  Fedora, cuyos arreglos no tienen `insert()`.
- La documentación describe las funciones en sus propios términos.

## 0.7 — 2026-11-17

- **Encabezados y pies** (`headfoot.py`, `py-foliation header-footer`):
  posiciones izquierda, centro y derecha; variables (`$page`,
  `$pagelabel`, `$bookmark`, `$totalpages`, `$author`, `$filename`,
  `$filepath`, la fecha y la hora, `$bates`); márgenes en in, cm o pt, y
  reducción de las páginas para dejar sitio; las fuentes estándar de PDF,
  tamaño, color, negrita, cursiva, borde y fondo; todas las páginas, las
  pares, las impares o una lista; numeración Bates; perfiles en
  `header-footer.json`.
- Se dibujan en un flujo de contenido propio, marcados como artefactos
  de paginación y derechos en las páginas giradas, y pueden quitarse, lo
  que devuelve la página exactamente como estaba.
- En la ventana: Pages > Header and Footer (Páginas > Encabezado y pie de
  página), con un diálogo y una vista previa; se escriben con Save, y se
  pueden deshacer y rehacer.

## 0.6.4 — 2026-11-14

- Hace falta Python 3.15 o posterior (antes, 3.13); la AppImage trae
  Python 3.15, y Copr ya no construye para Fedora 44.

## 0.6.3 — 2026-11-14

- Hace falta Python 3.13 o posterior (antes, 3.12).

## 0.6.2 — 2026-11-14

- Ya no hay Flatpak: se eliminan el manifiesto, `tools/flatpak-deps.py`,
  `packaging/FLATHUB.org` y su prueba (nunca se envió).
- Un inglés y un español más llanos en la documentación y en los
  comentarios del código; el código no cambia.

## 0.6.1 — 2026-11-13

- La vista previa podía colgar la ventana con algunos tamaños: una barra
  de desplazamiento achicaba la página, con lo que la barra dejaba de
  hacer falta, y así sin fin. La vista previa ajustada ya no tiene barras
  de desplazamiento.

## 0.6 — 2026-11-13

- La vista al abrir el archivo es ahora una Page layout (Disposición de
  página: Single, Single Continuous, Facing, Facing Continuous, Cover,
  Cover Continuous) y una Page view (Vista de página: Actual Size, Fit to
  Width, Fit to Page), como submenús del menú de las páginas y del menú
  View. Desaparecen el diálogo, el panel y los zooms menos usados; lo que
  no se ofrece se conserva tal como lo tiene el archivo.
- `py-foliation view`: `--page-view` (`--zoom` sigue funcionando) y los
  nuevos nombres de disposición; ya no hay `--panel`.
- Settings > Language (Ajustes > Idioma) en lugar de Interface Language.

## 0.5 — 2026-11-13

- **La vista al abrir el archivo**: `view.py` lee y escribe
  `/PageLayout`, `/PageMode` y `/OpenAction`, y solo cambia las partes
  que se piden. `py-foliation view` la muestra o fija `--layout`,
  `--zoom`, `--panel` y `--open-at`; `show` la imprime. En la ventana,
  File > View when opened, y "Open the document at page N".
- Todas las órdenes aceptan archivos después de las opciones, no solo
  `set`.

## 0.4 — 2026-11-13

- El código se divide en módulos más pequeños (`numbers.py`, `files.py`,
  `gui/widgets.py`, `gui/thumbnails.py`), que comparten la línea de
  órdenes y la ventana. Para el usuario no cambia nada.

## 0.3 — 2026-11-12

- En la ventana, a las páginas elegidas en la lista (Shift, Ctrl) se les
  puede, desde un menú del clic derecho, poner números a todas de una
  vez, seguir la numeración de la página anterior, dar una sola
  etiqueta, cambiar las etiquetas una por una o dejarlas sin etiqueta;
  sus etiquetas pueden copiarse.

## 0.2 — 2026-11-12

- **Folios** (1r, 1v, 2r …) y **sufijos** ([i], 12bis): los intervalos
  que PDF no puede expresar se escriben con una etiqueta por página y se
  reconocen de nuevo al leer el archivo.
- `set --from-file`, y Labels from a list (Etiquetas de una lista) en la
  ventana: el menor número de intervalos que dan una lista de etiquetas,
  una por página.
- `copy` da a unos PDF las etiquetas de otro; `set`, `clear` y `copy`
  aceptan varios archivos, `--dry-run` y `--password`.
- Al guardar se conserva el cifrado de un PDF: la 0.1 quitaba la
  protección de los archivos que cambiaba.
- `show --label`; autocompletado para bash, fish y zsh; páginas de
  manual en inglés y en español.
- En la ventana: una columna de sufijos, miniaturas de las páginas, ir a
  una página por su etiqueta y una petición de contraseña.
- Metadatos para PyPI y `release.py --pypi`; el RPM instala las páginas
  de manual, el autocompletado y los metadatos de AppStream.

## 0.1 — 2026-11-12

- Primera versión: py-foliation cambia las etiquetas de página de
  documentos PDF, la numeración que un visor muestra para sus páginas.
  Lee y escribe el árbol `/PageLabels` y da el menor número de
  intervalos.
- Línea de órdenes: `show` (con `--all`), `set` (intervalos como
  `PAGES:STYLE[:START[:PREFIX]]` o `--range`, `--keep`, `--remove`,
  `--in-place`), `clear` e `interface`.
- Una ventana (`py-foliation-gui`): una tabla de intervalos que se editan
  en su sitio, cada página con su etiqueta, una vista previa, deshacer y
  rehacer, archivos recientes.
- Interfaz en inglés y en español.
- `py-foliation-install` añade la ventana al menú de aplicaciones; una
  AppImage, un RPM firmado y paquetes en Copr; `tools/release.py` publica
  una versión en GitHub, Codeberg y Copr.
