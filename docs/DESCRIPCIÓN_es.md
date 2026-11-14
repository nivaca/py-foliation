# py-foliation 0.6.2: descripción

## Análisis

py-foliation cambia las etiquetas de página de documentos PDF: la numeración que un visor de PDF muestra para sus páginas. Un libro cuyas páginas preliminares van numeradas i, ii, iii … y cuyo texto empieza de nuevo en 1, con un apéndice A, B, C … y una tapa sin número, puede mostrar esos números en el visor, en su casilla de página y en su lista de páginas, en lugar del simple 1, 2, 3 … de las páginas del archivo. Lo hizo Nicolas Vaughan en 2026.

Tiene una ventana, para ver y editar las etiquetas página por página, y una línea de órdenes, para hacer lo mismo en scripts, en inglés o en español. py-foliation es software libre, bajo la Licencia Pública General de GNU, versión 3 o posterior. Acompaña a py-imposition, del mismo autor, y sigue su estructura y sus convenciones.

Los requisitos quedaron claros desde el principio. Lo primero era no tocar nada más que las etiquetas: las páginas, su contenido y el resto del documento tenían que quedar como estaban. Lo segundo, que las etiquetas se pudieran escribir con rapidez en la línea de órdenes, con una forma corta para quien la conoce y otra que se explique sola, y que pudieran verse y corregirse página por página en una ventana. También debía leer los árboles de etiquetas que de verdad tienen los PDF, por raros que sean, y estar en inglés y en español.

## Diseño

El programa está dividido en módulos pequeños, cada uno con un solo trabajo. `labels.py` es la base: los intervalos de etiquetas, la lectura de los intervalos en sus dos formas y de los números de página, el cálculo de los cambios y la lectura y escritura del árbol `/PageLabels`; los números en cada estilo están en `numbers.py`. `view.py` lee y escribe la vista del documento al abrirse, y `files.py` abre y guarda los PDF y lee las listas de etiquetas, para la línea de órdenes y la ventana por igual. `cli.py` es la línea de órdenes, con las órdenes `show`, `set`, `clear`, `copy`, `view`, `completion` e `interface`, y `completion.py` hace a partir de ella los scripts de completado de bash, fish y zsh. La ventana está en `gui/window.py`, con sus controles y diálogos en `gui/widgets.py` y las miniaturas en `gui/thumbnails.py`.

De los idiomas se ocupa `interface.py`, con `tr()`, que traduce cada texto del programa a partir de `locale/es.xml`, y `config.py` lee y escribe el archivo de configuración, `config.toml`, con el idioma de la interfaz; los dos vienen de py-imposition, como `install.py`, que añade la entrada del menú de aplicaciones en Linux, Windows y macOS.

Fuera del paquete quedan las herramientas: `tools/screenshots.py` hace las capturas de los README, `tools/icons.py` hace todos los iconos a partir de un SVG, `tools/bundle-appimage.py` arma la AppImage, `packaging/build-rpm.sh` el RPM firmado, y `tools/release.py` publica cada versión.

## Implementación

Está escrito en Python 3.12 o superior, con pikepdf (basada en QPDF), que lee y escribe los PDF. La ventana usa PySide6 (Qt 6), con QtPdf para mostrar las páginas. Son 16 módulos, unas 3400 líneas, y 7 órdenes.

Un PDF guarda sus etiquetas de página en un árbol de números, `/PageLabels`, en su catálogo. Cada entrada empieza un intervalo en una página e indica su estilo (números arábigos, romanos en minúscula o en mayúscula, letras minúsculas o mayúsculas, o ningún número), un prefijo y el número de su primera página; el intervalo dura hasta que empieza el siguiente. El programa lee ese árbol como venga (en un nodo o en muchos, con entradas más allá del documento, estilos desconocidos o nodos que aparecen dos veces, cosas que tienen los archivos reales) y lo escribe de nuevo como un solo nodo sencillo.

Dentro del programa, las etiquetas son una lista ordenada de intervalos, siempre con uno en la página 1. Todo cambio se hace de la misma manera: la lista se convierte en el estilo, el prefijo y el número de cada página, el cambio se hace página por página, y las páginas se vuelven a reunir en el menor número de intervalos que las dé. Así ningún cambio tiene que razonar sobre cómo se solapan los intervalos, y dos intervalos que numeran las páginas igual se vuelven uno.

### La línea de órdenes

`py-foliation show` lista los intervalos de un archivo, o con `--all` la etiqueta de cada página, e imprime la orden que da las mismas etiquetas a otro archivo. `set` da a un archivo nuevas etiquetas, `clear` las quita, e `interface` elige el idioma. Un intervalo se escribe de una de dos maneras: corta, `PÁGINAS:ESTILO[:INICIO[:PREFIJO]]` (`1:r`, `9:D`, `215:D:1:Ap-`), o con nombres, `--range PÁGINAS style=E start=N prefix=P`. Las páginas pueden contarse desde el final (`LAST`, `LAST-2`).

Un intervalo sin última página sigue hasta el siguiente; un tramo (`90-95:A`) se pone sobre los demás, y después de él las páginas siguen con los números que habrían tenido, de modo que se puede poner un apéndice en medio de una numeración sin romperla. `set` reemplaza las etiquetas que tenía el archivo, salvo con `--keep`, y `--remove PÁGINA` quita un intervalo, y el anterior sigue sobre sus páginas. El resultado va a un archivo nuevo (`libro-labelled.pdf`), salvo con `--in-place`.

### La ventana

La ventana muestra los intervalos en una tabla, cada uno con su primera página, su estilo, el número en que empieza y su prefijo, que se pueden cambiar allí mismo; debajo, cada página del archivo con su etiqueta; y a la derecha, la página elegida. *Añadir un intervalo* empieza uno en la página mostrada, *Quitar el intervalo* deja que el anterior siga y *Sin etiquetas* las quita todas. Cada cambio se puede deshacer y rehacer, y la ventana muestra la línea de órdenes que da las mismas etiquetas a un archivo.

*Guardar* da al archivo abierto sus nuevas etiquetas: escribe un archivo nuevo a su lado y solo entonces lo pone en su lugar, de modo que un error al guardar nunca deja un archivo roto. *Guardar como…* guarda una copia. Mientras haya cambios sin guardar, la barra de título muestra un asterisco, y la ventana pregunta antes de cerrarse o de abrir otro documento. Recuerda su tamaño y los últimos diez documentos abiertos.

### Folios, sufijos y listas

PDF numera las páginas en cinco estilos, con un prefijo, y nada más. Los libros para los que se hizo py-foliation necesitan más: los manuscritos y los impresos antiguos se cuentan en folios, el recto y el verso de cada hoja (1r, 1v, 2r …), y las ediciones marcan entre corchetes las páginas sin número ([i]) o añaden hojas (12bis). Por eso un intervalo puede tener un sexto estilo, los folios, y un sufijo después del número. Un intervalo así es *virtual*: se escribe en el archivo como una etiqueta para cada página, que cualquier visor muestra tal cual, y se encuentra de nuevo al leer el archivo. Para encontrarlo, cada etiqueta se lee como un prefijo, un número en algún estilo y un sufijo, de todas las maneras posibles, y se elige la lectura que continúa la etiqueta anterior; donde ninguna lo hace, la página conserva su etiqueta como texto.

La misma lectura convierte cualquier lista de etiquetas, una para cada página, en el menor número de intervalos que las da: `--from-file` en la línea de órdenes, y *Etiquetas de una lista…* en la ventana, leen la lista que escribe `show --all` (o *Guardar las etiquetas como lista…*), de modo que las etiquetas pueden editarse en cualquier editor u hoja de cálculo y volver a leerse.

Lo demás lo pidió el uso. `copy` da a unos archivos las etiquetas de otro, como cuando un libro se exporta de nuevo; `set`, `clear` y `copy` aceptan varios archivos a la vez, y `--dry-run` solo muestra lo que harían; `show --label` y *Ir a la página con la etiqueta…* de la ventana buscan una página por su etiqueta. La ventana puede mostrar las páginas en miniatura con sus etiquetas, y un doble clic en una página empieza allí un intervalo. Las páginas elegidas en la lista (con Mayús y Ctrl) pueden numerarse de una vez, en cualquier estilo, seguir la numeración de la página anterior, recibir una sola etiqueta o reetiquetarse una por una, desde un menú del botón derecho. Los PDF protegidos se abren con su contraseña y conservan su protección al guardarlos (la primera versión se la quitaba). La línea de órdenes completa sus órdenes y opciones en bash, fish y zsh, y tiene una página de manual, hecha a partir de su propia ayuda para que ambas coincidan siempre. El programa puede publicarse también en PyPI. (También se hizo un Flatpak para Flathub, pero se abandonó antes de enviarlo.)

### La vista al abrir

Además de sus etiquetas, un PDF puede decir cómo deben mostrarlo los visores al abrirlo, su *vista inicial*: la disposición de página, la vista de página y la página en que empezar. Las nombra como Xodo y otros visores: las disposiciones Una página, Una página continua, Páginas enfrentadas (dos páginas una junto a otra, las impares a la izquierda), Páginas enfrentadas continuas, Portada (como Páginas enfrentadas, con la primera página sola, como la portada de un libro) y Portada continua; las vistas de página Tamaño real, Ajustar al ancho y Ajustar a la página. Esto se guarda para todo el documento, no para cada página o intervalo, en el catálogo: `/PageLayout` y `/OpenAction`; no hay manera de dar a una página una disposición propia que algún visor siga. `view.py` los lee y los escribe, y cambia solo las partes que se piden, de modo que lo que no entiende, como un script de apertura o el panel junto a las páginas, se conserva salvo que se reemplace.

`py-foliation view` muestra la vista de un archivo o establece las partes que se den (`--layout`, `--page-view`, `--open-at`; `default` deja una parte al visor), y `show` la muestra con las etiquetas. En la ventana, el menú de las páginas y el menú *Ver* tienen los submenús *Disposición de página* y *Vista de página*, y ofrecen abrir el documento en la página elegida; la vista se deshace, se rehace y se guarda junto con las etiquetas. (La versión 0.5 establecía también el panel y más zooms, desde un diálogo; resultó confuso, y la 0.6 se limita a estos.)

La versión 0.6.1 corrigió un bloqueo que venía desde el principio. La vista previa muestra una página ajustada a su marco, y se dejaba a Qt decidir cuándo mostrar sus barras de desplazamiento; en algunos tamaños de la ventana, una barra achicaba la página, con lo que dejaba de hacer falta y se ocultaba, lo que agrandaba la página y la volvía a hacer necesaria, sin fin, y la ventana dejaba de responder. Una página ajustada a su marco no necesita barras, así que la vista previa no las tiene.

### Los idiomas

Cada texto del programa, en la ventana y en la línea de órdenes, incluidos los mensajes propios de `argparse`, pasa por `tr()`, y las traducciones están en un solo archivo XML, `locale/es.xml`, con cada texto en inglés y en español. El idioma se elige en la ventana (*Ajustes*), con `--interface` en la línea de órdenes o en `config.toml` (`py-foliation interface es` lo guarda). El README tiene una versión en español, paralela a la inglesa, y las capturas se hacen en los dos idiomas.

### Proceso y distribución

El trabajo pasó por siete etapas: primero las etiquetas mismas, su lectura, su escritura y el cálculo de los cambios; luego la línea de órdenes, con las dos formas de escribir los intervalos; después la ventana; la interfaz en español, el icono y las capturas; los paquetes (versión 0.1); los folios, los sufijos, las listas de etiquetas y lo que pidió el uso (versiones 0.2 y 0.3); y por último una reorganización del código en módulos más pequeños (0.4) y la vista al abrir (0.5, y en los términos de Xodo, 0.6).

La AppImage lleva su propio Python, con py-foliation, pikepdf y PySide6, y funciona en casi cualquier Linux; su primer argumento decide entre la ventana y la línea de órdenes. Antes de guardarla se arranca una vez con una carpeta personal vacía, para que no dependa de nada instalado en el equipo donde se hizo. Para Fedora hay un RPM, hecho con el Python, pikepdf y PySide6 de Fedora, que corre todas las pruebas mientras se construye y se firma con la clave del autor. `tools/release.py` publica cada versión de la misma manera: corre las pruebas, hace la wheel, el paquete fuente, la AppImage y el RPM firmado, etiqueta la versión y la publica en GitHub, en Codeberg y en Copr.

## Validación

Hay 104 pruebas automáticas (`tests/`), que se corren con `uv run pytest`. Comprueban los números en cada estilo, la lectura de los intervalos en sus dos formas y de los números de página, cómo se ponen unos intervalos sobre otros, la lectura y escritura del árbol de etiquetas, incluidos árboles raros, los intervalos que se encuentran en listas de etiquetas, y la vista al abrir, escrita y vuelta a leer en todas sus formas, conservando lo que el programa no entiende. La línea de órdenes se ejecuta de principio a fin sobre el documento de ejemplo, docs/example/numbers-100.pdf, cuyas páginas muestran cada una su número, y sobre entradas erróneas. La ventana se prueba sin pantalla, con la plataforma offscreen de Qt: abrir, editar, deshacer, guardar, guardar como, los cambios sin guardar, la vista al abrir, el idioma, y que la vista previa se asiente en cualquier tamaño de la ventana. Otras pruebas comprueban que cada texto tenga su traducción y que no sobre ninguna, el instalador del menú en cada sistema, los archivos de empaquetado y la clave de firma. Las pruebas corren con cada push en GitHub Actions.

## Plataforma

Funciona en Linux. Necesita Python 3.12 o superior y pikepdf, y para la ventana PySide6. Al ser Python y Qt, debería funcionar también en Windows y macOS, pero allí solo se ha probado con las pruebas automáticas. No necesita internet ni permisos de administrador.

## Ambiente

Lo desarrollé en Fedora Linux 45 con KDE Plasma, con Python 3.15 y uv, y con git. El icono se dibuja con Inkscape y las pruebas corren también en GitHub Actions.

Desde el código fuente, `uv sync --extra gui` lo prepara; `py-foliation-gui` abre la ventana, `py-foliation` es la línea de órdenes y `py-foliation-install` añade el acceso al menú de aplicaciones, con su icono. Los ajustes quedan en la carpeta de configuración del usuario (`~/.config/py-foliation/` en Linux).
