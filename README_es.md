# py-foliation

*[Read in English](README.md)*

py-foliation cambia las **etiquetas de página** de documentos PDF: la
numeración que un visor de PDF muestra para sus páginas. Un libro cuyas
páginas preliminares van numeradas i, ii, iii … y cuyo texto empieza de nuevo
en 1 puede mostrar esos números en el visor, en lugar del simple 1, 2, 3 … de
las páginas del archivo. Solo cambian las etiquetas; las páginas quedan como
están.

También puede añadir encabezados y pies a las páginas (la etiqueta de la
página, su número, la fecha, números Bates o cualquier texto), y esos sí
cambian las páginas. Tiene una ventana, para ver y editar las etiquetas página por página, y una
línea de órdenes, para hacer lo mismo en scripts.

## Instalación

Hay tres formas de instalarlo: la AppImage (no hay nada que instalar), el
paquete de Fedora, o desde el código fuente.

### AppImage (cualquier Linux)

Descargue `py-foliation-VERSION-x86_64.AppImage` de las
[versiones publicadas](https://github.com/nivaca/py-foliation/releases),
hágala ejecutable y ejecútela. Lleva su propio Python, Qt y todo lo demás, y
funciona en Linux con glibc 2.34 o posterior (Ubuntu 22.04, Debian 12, Fedora
35 y posteriores).

```bash
chmod +x py-foliation-*-x86_64.AppImage
./py-foliation-*-x86_64.AppImage                    # la ventana
./py-foliation-*-x86_64.AppImage show libro.pdf     # la línea de órdenes
./py-foliation-*-x86_64.AppImage cli --help         # la lista de órdenes
```

Un primer argumento que sea una orden (`show`, `set`…), una opción o `cli`
ejecuta la línea de órdenes; cualquier otra cosa, o nada, abre la ventana.
Herramientas como AppImageLauncher o Gear Lever la añaden al menú de
aplicaciones.

### Fedora (Copr)

```bash
sudo dnf copr enable nivaca/py-foliation
sudo dnf install py-foliation
```

Esto instala `py-foliation`, `py-foliation-gui`, una entrada de menú (ofrecida
también para abrir archivos PDF) y los iconos, con el Python, pikepdf y
PySide6 del propio Fedora. Las actualizaciones llegan con `sudo dnf upgrade`.
Los paquetes los construye y firma
[Copr](https://copr.fedorainfracloud.org/coprs/nivaca/py-foliation/).

Cada versión publicada incluye además el RPM, firmado con la clave del autor,
y esa clave (`RPM-GPG-KEY-py-foliation`, también en el repositorio como
[`packaging/RPM-GPG-KEY-py-foliation`](packaging/RPM-GPG-KEY-py-foliation)).
Su huella es `8187 0643 CA22 1AF9 0C30 554E BE68 32CD 3599 4948`:

```bash
sudo rpm --import RPM-GPG-KEY-py-foliation
sudo dnf install ./py-foliation-*.noarch.rpm
```

### Desde el código fuente

Se necesitan Python 3.15 o posterior y [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/nivaca/py-foliation.git    # o https://codeberg.org/nivaca/py-foliation.git
cd py-foliation
uv sync --extra gui      # sin --extra gui, solo la línea de órdenes
uv tool install '.[gui]' # opcional: py-foliation y py-foliation-gui disponibles en todas partes
py-foliation-install     # opcional: añade la ventana al menú de aplicaciones
```

`py-foliation-install` funciona en Linux, Windows y macOS, en sus propias
carpetas; `--uninstall` quita lo que añadió.

## La ventana

    py-foliation-gui [archivo.pdf]

![La ventana](https://raw.githubusercontent.com/nivaca/py-foliation/main/docs/img/gui_window_es.png)

Abra un PDF (o suéltelo en la ventana). La ventana muestra los **intervalos**
de etiquetas, cada uno con su primera página, su estilo (1, 2, 3; i, ii, iii;
I, II, III; a, b, c; A, B, C; folios 1r, 1v, 2r; o sin número), el número en
que empieza, un prefijo y un sufijo; debajo, cada página con su etiqueta; y a
la derecha, la página elegida.

![Folios, con miniaturas de las páginas](https://raw.githubusercontent.com/nivaca/py-foliation/main/docs/img/gui_folios_es.png)

- **Añadir un intervalo** empieza un nuevo intervalo en la página mostrada, y
  también un doble clic en una página; **Quitar el intervalo** deja que el
  anterior siga sobre sus páginas; **Sin etiquetas** las quita todas.
- Seleccione páginas en la lista (con Mayús y Ctrl) y haga clic derecho en
  ellas para **numerarlas** (en cualquier estilo, desde cualquier inicio, con
  prefijo y sufijo), **seguir la numeración anterior**, **darles una sola
  etiqueta**, **editar sus etiquetas una por una** o dejarlas **sin
  etiqueta**.
- El mismo menú establece cómo muestran los visores el documento al abrirlo
  (para todo el documento: PDF no tiene otra manera). **Disposición de
  página**: Una página, Una página continua, Páginas enfrentadas (dos páginas
  una junto a otra, las impares a la izquierda), Páginas enfrentadas
  continuas, Portada (como Páginas enfrentadas, con la primera página sola,
  como la portada de un libro) o Portada continua; **Vista de página**: Tamaño real,
  Ajustar al ancho o Ajustar a la página; y **Abrir el documento en la
  página N**. También están en el menú **Ver**, y se guardan con las
  etiquetas.
- **Ver ▸ Miniaturas de las páginas** muestra las páginas en miniatura con sus
  etiquetas, para revisar todo un libro de un vistazo.
- **Ir a la página con la etiqueta…** (Ctrl+L) busca una página por su
  etiqueta: `xii`, `12v`, `A-3`.
- **Editar ▸ Deshacer / Rehacer** van y vienen por los cambios.
- **Archivo ▸ Guardar** da las nuevas etiquetas al archivo abierto;
  **Guardar como…** guarda una copia con ellas; **Volver a las etiquetas del
  archivo** descarta los cambios.
- **Archivo ▸ Copiar las etiquetas de otro PDF…** las toma de otro archivo,
  por ejemplo de una exportación anterior del mismo libro.
- **Archivo ▸ Etiquetas de una lista…** lee la etiqueta de cada página de un
  archivo de texto, una en cada línea, y **Guardar las etiquetas como
  lista…** escribe uno, para editarlo en cualquier editor u hoja de cálculo.
- **Editar ▸ Copiar línea de órdenes** copia la orden que da las mismas
  etiquetas a otro archivo.
- **Páginas ▸ Encabezado y pie de página ▸ Añadir…** escribe un encabezado y
  un pie en las páginas, y **Páginas ▸ Marca de agua ▸ Añadir…** una marca de
  agua; el menú de las páginas lo hace en las elegidas (véanse [Encabezados y
  pies de página](#encabezados-y-pies-de-página) y [Marcas de
  agua](#marcas-de-agua)). Se ven enseguida en la vista previa y se escriben
  al guardar el archivo. Una página puede tener varios: el diálogo pregunta si
  conservar los que tiene. **Actualizar…** cambia la configuración del último
  añadido, **Quitar todos** quita los que añadió py-foliation, y **Quitar los
  números Bates** solo los encabezados y pies con números Bates. Los perfiles
  marcados con **Mostrar en el menú** también aparecen allí, para aplicarlos
  con un clic.
- **Páginas ▸ En varios archivos…** añade o quita encabezados y pies, números
  Bates o marcas de agua en una lista de PDF a la vez, en el orden de la lista
  (los números Bates siguen de un archivo al siguiente), y los guarda junto a
  cada archivo, en otra carpeta o sobre los propios archivos, con un texto
  antes o después de sus nombres.

Los archivos protegidos con contraseña la piden, y conservan su protección al
guardarlos.

## La línea de órdenes

![La línea de órdenes](https://raw.githubusercontent.com/nivaca/py-foliation/main/docs/img/cli_es.png)

    py-foliation show libro.pdf                     # los intervalos de etiquetas
    py-foliation show --all libro.pdf               # la etiqueta de cada página
    py-foliation show --label xii libro.pdf         # la página con la etiqueta xii
    py-foliation set libro.pdf 1:r 9:D              # nuevas etiquetas -> libro-labelled.pdf
    py-foliation set libro.pdf 1:r 9:D -i           # cambiar el propio libro.pdf
    py-foliation set *.pdf 1:r 9:D -i               # varios archivos a la vez
    py-foliation set libro.pdf 1:r 9:D --dry-run    # solo mostrar lo que haría
    py-foliation copy viejo.pdf nuevo.pdf -i        # las etiquetas de viejo.pdf, a nuevo.pdf
    py-foliation clear libro.pdf -o simple.pdf      # sin etiquetas
    py-foliation view libro.pdf                     # cómo se abre en un visor
    py-foliation header-footer libro.pdf --footer-center '$pagelabel' -i   # un pie de página
    py-foliation watermark libro.pdf --text BORRADOR --opacity 30% -i     # una marca de agua

Un intervalo se escribe `PÁGINAS:ESTILO[:INICIO[:PREFIJO]]`:

| Intervalo      | Páginas              | Etiquetas                    |
|----------------|----------------------|------------------------------|
| `1:r`          | desde la 1           | i, ii, iii …                 |
| `9:D`          | desde la 9           | 1, 2, 3 …                    |
| `201-214:A`    | de la 201 a la 214   | A … N, luego sigue la numeración anterior |
| `215:D:1:Ap-`  | desde la 215         | Ap-1, Ap-2 …                 |
| `5:f:12v`      | desde la 5           | 12v, 13r, 13v … (folios)     |
| `LAST:-::Tapa` | la última página     | Tapa                         |

o, con `--range`, como `PÁGINAS [style=E] [start=N] [prefix=P] [suffix=X]`:

    py-foliation set libro.pdf --range 1-8 style=roman --range 9- style=arabic
    py-foliation set libro.pdf --range 1-4 style=roman 'prefix=[' 'suffix=]' 5:D

`PÁGINAS` es una primera página (`9`) o un tramo (`9-200`, `9..200`, `201-`);
`LAST` y `LAST-N` cuentan desde el final. Un intervalo sin última página sigue
hasta el siguiente; un tramo se pone sobre los demás, y después de él las
páginas siguen con los números que tenían.

Los estilos son `D` o `arabic` (1, 2, 3), `r` o `roman` (i, ii, iii), `R` o
`ROMAN` (I, II, III), `a` o `letters` (a, b, c), `A` o `LETTERS` (A, B, C), `f`
o `folio` (1r, 1v, 2r: el recto y el verso de cada hoja; el inicio es una hoja
y su lado, como `12v`), y `-` o `none` (solo el prefijo).

`set` reemplaza las etiquetas que tenía el archivo; con `--keep` cambia solo
las páginas indicadas, y `--remove PÁGINA` quita el intervalo que empieza en
PÁGINA. `show` imprime la orden que da las etiquetas de un archivo a otro.
`--password` abre archivos protegidos, que conservan su protección.

### Folios, sufijos y cualquier otra etiqueta

PDF numera las páginas en cinco estilos, con un prefijo. Los folios, para
manuscritos e impresos antiguos, y las etiquetas con algo después del número
(`[i]`, `12bis`) no están entre ellos: py-foliation los escribe como una
etiqueta para cada página, y los reconoce de nuevo al leer el archivo, de
modo que se muestran y se editan como intervalos, igual que los demás.

Cualquier numeración puede darse página por página: `--from-file` (o
**Archivo ▸ Etiquetas de una lista…**) lee la etiqueta de cada página, una en
cada línea, y encuentra el menor número de intervalos que las da:

    py-foliation show --all libro.pdf > etiquetas.txt    # editar etiquetas.txt…
    py-foliation set libro.pdf --from-file etiquetas.txt -i

### La vista al abrir el archivo

Un PDF puede decir cómo deben mostrarlo los visores al abrirlo (su *vista
inicial*): la disposición de página, la vista de página y la página en que
empezar. Tiene una sola vista para todo el documento, no una por página.
`view` la muestra, y establece las partes que se den (las demás se conservan;
`default` deja una parte al visor):

    py-foliation view libro.pdf --layout cover --page-view fit-page --open-at 9 -i
    py-foliation view libro.pdf --page-view actual-size -i
    py-foliation view libro.pdf --open-at default -i

Las disposiciones de página son `single` (una página cada vez),
`single-continuous` (todas las páginas en una columna), `facing` (dos páginas
cada vez, las impares a la izquierda), `facing-continuous`, `cover` (como
`facing`, con la primera página sola, como la portada de un libro) y
`cover-continuous`; las vistas de página, `actual-size` (tamaño real),
`fit-width`, `fit-page` o un porcentaje (`150%`). `show` también muestra la
vista, si el archivo tiene una.

### Encabezados y pies de página

Un encabezado y un pie de página tienen tres lugares cada uno: izquierda,
centro y derecha. Su texto puede llevar variables: `$page` (la página del
archivo), `$pagelabel`, `$bookmark` (el marcador bajo el que está la página),
`$totalpages`, `$author`, `$filename`, `$filepath`, `$date` (28 nov 2007, o
como diga `--date-format`: `long`, `d/m/yy`, `dd/mm/yyyy`, `yyyy-mm-dd` …),
`$shortdate`, `$time`, `$day`, `$month`, `$year`, `$shortyear`, `$hour`,
`$longhour`, `$minute`, `$second`, `$ampm` y `$bates`; `$$` escribe un `$`. En
la línea de órdenes, ese texto va entre comillas simples; si no, el shell
toma las variables como suyas:

    py-foliation header-footer libro.pdf --footer-center 'Página $pagelabel de $totalpages' \
        --header-right '$date' --pages 9- -i
    py-foliation header-footer libro.pdf --footer-right '$bates' --bates-prefix ABC- --odd -i
    py-foliation header-footer libro.pdf --remove -i

Las demás opciones:

- **Márgenes** (`--units in|cm|pt`, `--top`, `--bottom`, `--left`,
  `--right`): de los bordes de la página al encabezado, al pie y al texto de
  los lados. `--shrink` reduce el contenido de las páginas para que el
  encabezado y el pie no lo tapen.
- **Apariencia**: `--font helvetica|times|courier`, `--size`, `--color`,
  `--bold`, `--italic`, `--border` (con `--border-color` y `--border-width`)
  y `--background`.
- **Páginas**: `--pages` (`9-200`, `1,3,9-`; todas si no se da), y de esas,
  `--even` o `--odd`.
- **Numeración Bates**: `$bates` escribe `--bates-prefix`, un número desde
  `--bates-start` con al menos `--bates-digits` dígitos, y `--bates-suffix`,
  contando las páginas en que va.
- **Perfiles**: `--save-profile NOMBRE` guarda la configuración, `--profile
  NOMBRE` parte de ella, y `--list-profiles` y `--delete-profile` los
  administran. La ventana usa los mismos.

Las fuentes son las estándar de PDF, que todo visor tiene: escriben la
escritura latina, con sus acentos y signos, pero no la griega ni la
cirílica.

Un encabezado y pie añadidos a una página reemplazan los que py-foliation
había añadido antes, salvo que `--add` los conserve; así una página puede
tener varios. `--update` reemplaza el último añadido, partiendo de su propia
configuración (guardada en el archivo) con las opciones dadas encima.
`--remove` (o **Quitar todos**) deja las páginas exactamente como estaban,
enlaces incluidos, y `--remove-bates` quita solo los encabezados y pies con
números Bates. `show` lista lo que py-foliation añadió a un archivo.

Con varios archivos, los números Bates siguen de uno al siguiente, en el
orden en que se dan, y la orden dice qué número viene después, para empezar
con él el lote siguiente:

    py-foliation header-footer vol1.pdf vol2.pdf vol3.pdf --footer-right '$bates' \
        --bates-prefix ABC- --output-dir producidos
    Siguiente número Bates: ABC-000913

`--output-dir` guarda los archivos en otra carpeta, con sus propios nombres,
y `--name-prefix` y `--name-suffix` añaden un texto antes o después de los
nombres; todas las órdenes que escriben archivos tienen estas opciones.

### Marcas de agua

Una marca de agua es un texto, como BORRADOR o COPIA (que puede llevar las
mismas variables), o una página de otro PDF, delante del contenido de las
páginas o detrás:

    py-foliation watermark libro.pdf --text BORRADOR --opacity 30% --scale 60 -i
    py-foliation watermark libro.pdf --text 'Copia para $author' --rotation 0 \
        --vertical bottom --voffset 3 --no-screen -i
    py-foliation watermark libro.pdf --file sello.pdf --scale 15 --horizontal right \
        --vertical top --behind -i

- **Qué**: `--text`, con `--font`, `--size`, `--color`, `--bold` e
  `--italic`; o `--file`, un PDF, y `--file-page`, la página que se usa.
- **Apariencia**: `--scale` (el porcentaje de la página que ocupa; por
  defecto conserva su propio tamaño), `--rotation` (grados, en sentido
  contrario a las agujas del reloj; 45 por defecto), `--opacity` (de 0 a 1, o
  de 0% a 100%), `--behind` (detrás del contenido, donde una página pintada de
  blanco la tapa) y `--no-print` o `--no-screen` (solo en pantalla, o solo al
  imprimir, en los visores que siguen esas indicaciones).
- **Posición**: `--horizontal left|center|right` y `--vertical
  top|center|bottom` (el centro por defecto), desplazada por `--hoffset` y
  `--voffset` en `--units`.
- **Páginas**, **numeración Bates**, **perfiles**, `--add`, `--update` y
  `--remove`, como para los encabezados y pies.

### Completado y manual

`py-foliation completion bash|fish|zsh` imprime el script que completa
órdenes, opciones y archivos en cada shell, por ejemplo:

    py-foliation completion fish > ~/.config/fish/completions/py-foliation.fish

El paquete de Fedora los instala, junto con la página de manual
(`man py-foliation`).

## Idioma

La interfaz está en inglés y en español. `py-foliation interface es` (o
**Ajustes ▸ Idioma** en la ventana) guarda la elección en
el archivo de configuración; `--interface CÓDIGO` la cambia para una sola
ejecución.

## Desarrollo

    uv sync --all-extras
    uv run pytest

Las imágenes de este README las hace `uv run python tools/screenshots.py`
(en los dos idiomas, sin mostrar nada en la pantalla), y los iconos
`uv run python tools/icons.py` (con Inkscape) a partir de
`src/py_foliation/icons/py-foliation.svg`.

La AppImage la hace `uv run python tools/bundle-appimage.py`, el RPM firmado
`packaging/build-rpm.sh --sign`, y cada versión, en GitHub, Codeberg y Copr,
`uv run python tools/release.py --rpm` (vea `packaging/COPR.org`); `--pypi` la
sube además a PyPI. Las páginas de manual se hacen a partir de la ayuda de la
línea de órdenes con `uv run python tools/manpage.py` (una prueba comprueba
que estén al día).

## Licencia

GNU General Public License, versión 3 o posterior. Por
[Nicolas Vaughan](https://nicolasvaughan.org).
