# Pegasus Lesson07: natywne Exposure / Curvature na realnej Sa Calobra

**Stan:** Test gałęzi oryginalnego Houdiniego przeszedł w ograniczonym obszarze. To NIE jest pełny graf Pegasusa, produkcja 16k ani render UE.

## Dowód

- Native [run 39811690827](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39811690827): PASS. [Obrazy/BGEO/raport](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39811690827/artifacts/12439828015).
- Odczyt natywnych parametrów [run 39810470885](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39810470885): 83 pola Mask by Feature, 48 Visualize, 17 oryginalnego Tint HDA.
- Wejście: prawdziwy materiałowy wycinek 256x256 po pięciu oryginalnych Material HDA i czterech tintach w kolejności źródłowej, [run 39808914161](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39808914161).
- Wyniki: mask12 Exposure 65 536 niezerowych próbek; mask13 Curvature 44 220. Tint5 średnie linear RGB 0.1284523, 0.1197795, 0.0685445; Tint6 0.1670203, 0.1552188, 0.0893540. BGEO zapisano i otwarto ponownie, zachowując chronione oryginalne height/Alpha/maski po korekcie tylko w disposable scratch.

## Odwzorowana topologia źródłowa

1. Source Tint4 → heightfield_visualize4 (Default Tinting, No Change).
2. Visualize4 → heightfield_maskbyfeature12 (Occlusion ON, ViewDistance145, StepScale1, Searches16, Combine Replace, Invert Mask OFF).
3. Tint4 główne wejście Tint5, mask12 wejście nr 2; Gradient Tint5 Strength1, Mask puste, Ramp Layer mask.
4. mask12 → mask13, a NIE Tint5 → mask13. Mask13 Curvature ON, MaxCurvature0.18, Occlusion OFF, Combine Replace, Invert OFF.
5. Reopened Tint5 → główne Tint6; mask13 → wejście nr 2 Tint6. Gradient Tint6 Strength0.613.

## Parametry wideo kontra adaptacje

Wiadome punkty źródłowe: Exposure mask12 ramp P2 (1,1); Exposure Tint5 P2 (0.93538,RGB 0.651/0.651/0.651); Curvature Tint6 P2 (1,RGB 2/2/2). Reszta kompletnego zapisu ramp nie była odsłonięta na filmie. W proof użyto jawnie oznaczonych **YACS_ADAPTATION**: mask12 rampa liniowa (0,0)→(1,1); Tint5 P1 (0,RGB1), P3 (1,RGB1); mask13 rampa liniowa (0,0)→(1,1); Tint6 P1 (0,RGB1).

**Ważny limit:** ViewDistance145m jest większy od szerokości bieżącego wycinka 128m. Przy braku halo wynik okluzji przy brzegach jest niereprezentatywny dla pełnego świata. Produkcja wymaga rozszerzonego wejścia, testu dwóch sąsiadujących obszarów i globalnego world-space dopasowania.

Graficzny kontrakt Grass mask6/7/8 nie jest jeszcze pełny (obecny bounded canary używa Stage2 ramp_layer). Brakuje też potwierdzenia pełnego Stage3 upstream, odrębnego realnego sand>0, wszystkich 16k materiałowych exports, 3 UE arrays oraz świeżego native UE Lit. Bramka G04 **pozostaje BLOCKED** mimo natywnego dodatniego wyniku tej części.

Kod: scripts/houdini/l07_feature_native_contract.py, scripts/houdini/l07_exposure_curvature_canary.py, scripts/houdini/test_l07_exposure_curvature_canary.py. Ścisłe źródło video/source HDA: houdini-author-graph-followup-20261022.json.
