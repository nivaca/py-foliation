# py-foliation 1.0.1: descripción

## Análisis

py-foliation cambia las etiquetas de página de documentos PDF: la numeración que un visor de PDF muestra para sus páginas. Un libro cuyas páginas preliminares van numeradas i, ii, iii … y cuyo texto empieza de nuevo en 1, con un apéndice A, B, C … y una tapa sin número, puede mostrar esos números en el visor, en su casilla de página y en su lista de páginas, en lugar del simple 1, 2, 3 … de las páginas del archivo. Lo hizo Nicolas Vaughan en 2026.

Tiene una ventana, para ver y editar las etiquetas página por página, y una línea de órdenes, para hacer lo mismo en scripts, en inglés o en español. py-foliation es software libre, bajo la Licencia Pública General de GNU, versión 3 o posterior. Acompaña a py-imposition, del mismo autor, y sigue su estructura y sus convenciones.

Los requisitos quedaron claros desde el principio. Lo primero era no tocar nada más que las etiquetas: las páginas, su contenido y el resto del documento tenían que quedar como estaban. Lo segundo, que las etiquetas se pudieran escribir con rapidez en la línea de órdenes, con una forma corta para quien la conoce y otra que se explique sola, y que pudieran verse y corregirse página por página en una ventana. También debía leer los árboles de etiquetas que de verdad tienen los PDF, por raros que sean, y estar en inglés y en español.

## Diseño

El programa está dividido en módulos pequeños, cada uno con un solo trabajo. `labels.py` es la base: los intervalos de etiquetas, la lectura de los intervalos en sus dos formas y de los números de página, el cálculo de los cambios y la lectura y escritura del árbol `/PageLabels`; los números en cada estilo están en `numbers.py`. `view.py` lee y escribe la vista del documento al abrirse, `headfoot.py` dibuja los encabezados y pies de página y `watermark.py` las marcas de agua, sobre lo que comparten en `stamps.py` (con los anchos de las fuentes que da `fontmetrics.py`), y `files.py` abre y guarda los PDF y lee las listas de etiquetas, para la línea de órdenes y la ventana por igual. `cli.py` es la línea de órdenes, con las órdenes `show`, `set`, `clear`, `copy`, `view`, `header-footer`, `watermark`, `pages`, `completion` e `interface`, y `completion.py` hace a partir de ella los scripts de completado de bash, fish y zsh. La ventana está en `gui/window.py`, con sus controles y diálogos en `gui/widgets.py`, el diálogo de encabezados y pies en `gui/headfoot_dialog.py` y las miniaturas en `gui/thumbnails.py`.

De los idiomas se ocupa `interface.py`, con `tr()`, que traduce cada texto del programa a partir de `locale/es.xml`, y `config.py` lee y escribe el archivo de configuración, `config.toml`, con el idioma de la interfaz; los dos vienen de py-imposition, como `install.py`, que añade la entrada del menú de aplicaciones en Linux, Windows y macOS.

Fuera del paquete quedan las herramientas: `tools/screenshots.py` hace las capturas de los README, `tools/icons.py` hace todos los iconos a partir de un SVG, `tools/bundle-appimage.py` arma la AppImage, `packaging/build-rpm.sh` el RPM firmado, y `tools/release.py` publica cada versión.

## Implementación

Está escrito en Python 3.14 o superior, con pikepdf (basada en QPDF), que lee y escribe los PDF. La ventana usa PySide6 (Qt 6), con QtPdf para mostrar las páginas. Son 31 módulos, unas 9000 líneas, y 10 órdenes.

### Las etiquetas

Un PDF guarda sus etiquetas en un árbol de números, `/PageLabels`, en su catálogo; cada entrada empieza un intervalo e indica su estilo, un prefijo y el número de su primera página. El programa lee ese árbol como venga, con las rarezas que tienen los archivos reales, y lo escribe de nuevo como un solo nodo sencillo. Dentro del programa, las etiquetas son una lista ordenada de intervalos, siempre con uno en la página 1. Todo cambio se hace página por página, y las páginas se vuelven a reunir en el menor número de intervalos que las dé. Así ningún cambio tiene que razonar sobre cómo se solapan los intervalos.

En la línea de órdenes un intervalo se escribe en forma corta (`215:D:1:Ap-`) o con nombres (`--range`). En la ventana cada cambio se puede deshacer, y *Guardar* escribe un archivo nuevo al lado y solo entonces lo pone en su lugar, de modo que un error al guardar nunca deja un archivo roto.

Los cinco estilos de PDF no bastan para manuscritos e impresos antiguos, que se cuentan en folios (1r, 1v, 2r …), ni para las páginas entre corchetes ([i]) o añadidas (12bis). Por eso un intervalo puede tener un sexto estilo, los folios, y un sufijo. Un intervalo así es *virtual*: se escribe como una etiqueta para cada página y se encuentra de nuevo al leer el archivo, eligiendo, entre las lecturas posibles de cada etiqueta, la que continúa la anterior. La misma lectura convierte cualquier lista de etiquetas en intervalos, y así pueden editarse en una hoja de cálculo.

### Cambios en las páginas

Los encabezados y pies de página y las marcas de agua sí cambian las páginas. El texto se escribe en las fuentes estándar de PDF, Helvetica, Times y Courier, que todo visor tiene: no hay que incrustar nada, a cambio de escribir solo la escritura latina. Cada adición es una *capa* (`stamps.py`): un flujo de contenido propio, dibujado después del original, que se envuelve en `q … Q`, y un registro en el diccionario de la página con su clase y su configuración en JSON. Por eso cualquier capa puede quitarse, no solo la última, y la página queda exactamente como estaba.

Para PDF/A y PDF/X, `conform.py` escribe el archivo y se lo pasa a pdf2iso, otro programa del autor, si está instalado. Ghostscript conserva las etiquetas y la vista, pero escribe las páginas de nuevo y pierde los registros de las capas; de ahí que la ventana nunca ponga un PDF/A en lugar del archivo abierto.

`arrange.py` ordena las páginas: las mueve, borra, duplica y gira, e inserta páginas en blanco o de otro PDF. Cada operación dice, para cada página del resultado, qué página era; de esa única lista salen el nuevo árbol de páginas, las etiquetas y la página en que se abre el archivo. Las páginas conservan sus objetos, y sus marcadores, enlaces y capas van con ellas. Como PDF guarda las etiquetas por posición, el usuario elige si siguen a las páginas o se quedan donde están.

Desde la 1.0 las miniaturas las dibuja el renderizador de Qt, en un hilo de C++. Un hilo de Python no habría servido: PySide retiene el candado de Python mientras PDFium dibuja. Cada miniatura se guarda según lo que muestra, y mover páginas no obliga a redibujarla.

### Distribución

La AppImage lleva su propio Python, con py-foliation, pikepdf y PySide6. Para Fedora hay un RPM firmado, hecho con el Python, pikepdf y PySide6 de Fedora. En `installers/`, `install.sh` e `install.ps1` buscan Python 3.14 o posterior y ejecutan `install.py`, que solo necesita la biblioteca estándar: hace un entorno propio en las carpetas del usuario, instala el wheel de la última versión y pone la ventana en el menú de aplicaciones. `tools/release.py` corre las pruebas, hace los paquetes y publica cada versión en GitHub, Codeberg y Copr.

## Validación

Hay 162 pruebas automáticas (`tests/`), que se corren con `uv run pytest`. Comprueban los números en cada estilo, la lectura de los intervalos en sus dos formas y de los números de página, cómo se ponen unos intervalos sobre otros, la lectura y escritura del árbol de etiquetas, incluidos árboles raros, los intervalos que se encuentran en listas de etiquetas, y la vista al abrir, escrita y vuelta a leer en todas sus formas, conservando lo que el programa no entiende, y los encabezados y pies de página: sus variables, su lugar en la página, tal como lo lee pdftotext, también en páginas giradas, y su eliminación, que debe devolver las páginas byte por byte; varias capas en una página, quitar una de entre otras, actualizar, los archivos de la 0.7, marcas de agua de texto y de página, detrás y solo para imprimir, los formatos de fecha y los números Bates que siguen por varios archivos; también que se encuentre pdf2iso y, cuando está instalado, que las conversiones a PDF/A y PDF/X conserven las etiquetas. La línea de órdenes se ejecuta de principio a fin sobre el documento de ejemplo, docs/example/numbers-100.pdf, cuyas páginas muestran cada una su número, y sobre entradas erróneas. La ventana se prueba sin pantalla, con la plataforma offscreen de Qt: abrir, editar, deshacer, guardar, guardar como, los cambios sin guardar, la vista al abrir, el idioma, guardar una copia en PDF/X y su ajuste, que la vista previa se asiente en cualquier tamaño de la ventana, y que las miniaturas se conserven tras los cambios y caigan donde deben al soltarlas. Otras pruebas comprueban que cada texto tenga su traducción y que no sobre ninguna, el instalador del menú en cada sistema, los instaladores de `installers/` (sin descargar nada, en una carpeta personal propia), los archivos de empaquetado y la clave de firma. Las pruebas corren con cada push en GitHub Actions.

## Plataforma

Funciona en Linux. Necesita Python 3.14 o superior y pikepdf, y para la ventana PySide6. Al ser Python y Qt, debería funcionar también en Windows y macOS, pero allí solo se ha probado con las pruebas automáticas; para instalarlo con Python en esos sistemas (y en Linux) están los instaladores de `installers/`. Para PDF/A y PDF/X hace falta pdf2iso, con Ghostscript. No necesita internet ni permisos de administrador.

## Ambiente

Fue desarrollado en Fedora Linux 45 con KDE Plasma, con Python 3.15 y uv, y con git. El icono se dibuja con Inkscape y las pruebas corren también en GitHub Actions.

Desde el código fuente, `uv sync --extra gui` lo prepara; `py-foliation-gui` abre la ventana, `py-foliation` es la línea de órdenes y `py-foliation-install` añade el acceso al menú de aplicaciones, con su icono. Los ajustes quedan en la carpeta de configuración del usuario (`~/.config/py-foliation/` en Linux).
