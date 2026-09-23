# PKLot dataset attribution

PKLot is provided under **Creative Commons Attribution 4.0 International (CC BY 4.0)**.
See the [license deed](https://creativecommons.org/licenses/by/4.0/) and
[legal code](https://creativecommons.org/licenses/by/4.0/legalcode).

**Required credit:** Almeida, P., Oliveira, L. S., Silva Jr, E., Britto Jr, A.,
Koerich, A. *PKLot – A robust dataset for parking lot classification.*
Expert Systems with Applications, **42(11):4937–4949, 2015**.

Sources: [university dataset page](https://web.inf.ufpr.br/vri/databases/parking-lot-database/),
[authors' readme](https://www.inf.ufpr.br/lesoliveira/download/pklot-readme.pdf),
[paper](https://www.inf.ufpr.br/lesoliveira/download/ESWA2015.pdf).

The university host did not resolve on the development computer on 22 September
2026. Acquisition therefore uses the [teenygrad original-archive mirror](https://huggingface.co/datasets/teenygrad/pklot/tree/9604b05ad6dfd5ab5817b5fa6600d375754562fb),
revision `9604b05ad6dfd5ab5817b5fa6600d375754562fb`. Its dataset card states that
the archive is unmodified. The mirror's Git LFS SHA-256 pin is
`e89bbc1dc735298c478688d50c7a682fb3b0076a87b6634923132709f2d2fa9b`,
size **4,898,276,304 bytes**. This verifies the mirror's published artifact;
an independent publisher-side checksum was not available for comparison.

This project extracts only original **UFPR04** full images and XML. Original
images/XML are retained unchanged. Derived artifacts include fixed-slot JSON
recipes, day-based partition manifests, selected vacant reference copies,
fitted thresholds, annotations and experimental measurements. Derived files
retain this attribution. No author or institution endorsement is implied.

UFPR04 and UFPR05 are two views of the same UFPR car park; PUCPR is another car
park. This validation uses UFPR04 only. The dataset license does not alter the
separate licenses applicable to the application or the YOLO model weights.
