# fbds_database
Scripts to download and process (state level) FBDS database


Adapted from https://github.com/open-geodata/br_fbds/
Thanks Michel Metran https://github.com/michelmetran


Use 01_obter_dados_estado_FBDS.ipynb to download the .tar files and 
02_processar_dados_estado_FBDS.ipynb to process the data to each state (all municipalities to one specific geopackage).

| id  | _Layer_              | Subpasta    | Tamanho |
| :-- | :------------------- | :---------- | ------: |
| 1   | app.gpkg             | APP         |  994 MB |
| 2   | app_uso.gpkg         | APP         | 2,07 GB |
| 3   | hidro_simples.gpkg   | HIDROGRAFIA |  673 MB |
| 4   | hidro_duplas.gpkg    | HIDROGRAFIA | 93,8 MB |
| 5   | hidro_nascentes.gpkg | HIDROGRAFIA | 60,0 MB |
| 6   | hidro_massa.gpkg     | HIDROGRAFIA |  124 MB |
| 7   | uso.gpkg             | USO         | 3,89 GB |
|     | Total                |             | 7,87 GB |

<br>
