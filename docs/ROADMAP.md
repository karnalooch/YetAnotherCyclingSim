# YetAnotherCyclingSim — roadmapa

**Wersja:** 0.1  
**Status:** Draft  
**Tryb pracy:** 11–20 godzin tygodniowo  
**Cel krótkoterminowy:** grywalna wersja od startu do mety  
**Cel docelowy:** pełne MVP opisane w PRODUCT_REQUIREMENTS.md

## Zasady pracy

1. Każdy etap kończy się działającym rezultatem.
2. Nie rozpoczynamy kolejnego dużego modułu, dopóki obecny nie działa.
3. Najpierw poprawność, później wygląd i optymalizacja.
4. Kod generowany przez AI musi zostać uruchomiony i sprawdzony.
5. Jedna zmiana logiczna powinna odpowiadać jednemu commitowi.
6. Nie kupujemy assetów bez konkretnego zastosowania.
7. Nie dodajemy funkcji spoza wymagań MVP.
8. Co tydzień przygotowujemy działającą wersję projektu.
9. Płynność mierzymy regularnie na komputerze referencyjnym.
10. Każdy ważny wzór fizyczny otrzymuje test automatyczny.

## Realistyczne oczekiwania czasowe

Plan 12-tygodniowy jest wariantem ambitnym.

Przy braku wcześniejszego doświadczenia pełne MVP może wymagać więcej czasu. Po 12 tygodniach priorytetem jest kompletna i grywalna jazda, nawet jeśli część grafiki, animacji, pogody lub eksportu FIT będzie wymagała dalszego dopracowania.

Zakresu nie zwiększamy bez aktualizacji dokumentu wymagań i roadmapy.

---

# Etap 0 — fundament projektu

**Planowany czas:** tydzień 1

## Zadania

- [x] Utworzenie prywatnego repozytorium GitHub.
- [x] Dodanie `.gitignore` dla Unreal Engine.
- [x] Utworzenie dokumentu wymagań.
- [x] Utworzenie roadmapy.
- [x] Konfiguracja Git LFS.
- [x] Utworzenie zasad pracy dla asystentów AI.
- [ ] Utworzenie tablicy zadań.
- [x] Instalacja wymaganych narzędzi na komputerze domowym.
- [x] Utworzenie projektu Unreal Engine 5.
- [x] Uruchomienie pustego projektu na komputerze referencyjnym.

**Notatka statusowa:** na komputerze referencyjnym udało się zbudować projekt
UE 5.8 w trybie C++ (edytor, Windows) oraz uruchomić pusty projekt
YetAnotherCyclingSim.

## Kryterium ukończenia

- Repozytorium można sklonować na obu komputerach.
- Dokumentacja jest dostępna w repozytorium.
- Pusty projekt UE5 uruchamia się bez błędów.
- Projekt można zbudować na Windows.

---

# Etap 1 — prototyp fizyki poza grafiką

**Planowany czas:** tydzień 1–2

**Status:** ukończony

## Cel

Stworzyć testowalny model jazdy, zanim powstanie docelowa trasa i grafika.

## Zadania

- [x] Zdefiniowanie jednostek wszystkich parametrów.
- [x] Zdefiniowanie danych wejściowych i wyjściowych silnika fizycznego.
- [x] Implementacja masy kolarza i roweru.
- [x] Implementacja mocy i kadencji testowej.
- [x] Implementacja grawitacji.
- [x] Implementacja oporu toczenia.
- [x] Implementacja oporu aerodynamicznego.
- [x] Implementacja wiatru.
- [x] Implementacja przyspieszania i toczenia.
- [x] Zastosowanie stałego kroku czasowego.
- [x] Dodanie testów dla podjazdu, płaskiego odcinka i zjazdu.
- [x] Dodanie prostego rejestru wyników symulacji.

**Uwaga:** Referencyjny pakiet Pythona w katalogu `physics_reference/`
(kontrakty danych, siły, stały krok czasowy i testy jednostkowe) jest
ukończony i przechodzi **258 testów automatycznych**. Port C++ do Unreal
Engine jest ukończony: zawiera kontrakty danych, siły oporu,
deterministyczny krok symulacji oraz testy dynamiki długookresowej.
Budowa edytora UE 5.8 (Windows, Development) kończy się sukcesem,
a wszystkie cztery testy automatyczne `CyclingPhysics` przechodzą.
Etap 1 dostarcza czyste obliczenia ze stałym krokiem czasowym; akumulator
czasu w trakcie gry, który uniezależnia rozgrywkę od zmiennego FPS,
pozostaje częścią etapu 2. Prototypy Pythona dotyczące trasy, pogody
i zakrętów nie oznaczają jednak ukończenia późniejszych etapów Unreal
Engine — te etapy nadal wymagają implementacji i weryfikacji w UE5.

## Kryterium ukończenia

Dla ustalonych parametrów symulator oblicza powtarzalną prędkość i dystans, a wszystkie testy przechodzą automatycznie.

---

# Etap 2 — pierwszy grywalny prototyp UE5

**Planowany czas:** tydzień 2–3

## Cel

Połączyć wejście testowe, fizykę i ruch obiektu po prostej trasie.

## Zadania

- [ ] Utworzenie podstawowej mapy testowej.
- [ ] Utworzenie drogi opartej na spline.
- [ ] Dodanie tymczasowego obiektu reprezentującego rower.
- [ ] Poruszanie obiektu zgodnie z wynikiem silnika fizycznego.
- [ ] Sterowanie mocą i kadencją z klawiatury.
- [ ] Dodanie panelu diagnostycznego.
- [ ] Dodanie zatrzymania i ponownego uruchomienia jazdy.
- [ ] Dodanie stałego kroku fizyki niezależnego od FPS.
- [ ] Pomiar liczby FPS i czasu klatki.

## Kryterium ukończenia

Użytkownik może przejechać prostą trasę, zmieniając moc i kadencję, a prędkość wynika z modelu fizycznego.

---

# Etap 3 — trasa testowa i profil wysokości

**Planowany czas:** tydzień 3–5

## Cel

Stworzyć pełny przebieg fikcyjnej trasy alpejskiej.

## Zadania

- [ ] Zaprojektowanie profilu 20–30-minutowej jazdy.
- [ ] Utworzenie przebiegu od doliny do wysokich gór.
- [ ] Dodanie podjazdów, zjazdów i wypłaszczeń.
- [ ] Dodanie zakrętów o różnych promieniach.
- [ ] Obliczanie nachylenia z geometrii trasy.
- [ ] Utworzenie punktów startu, sektorów i mety.
- [ ] Dodanie podstawowego terenu.
- [ ] Sprawdzenie ciągłości drogi i braku gwałtownych zmian nachylenia.
- [ ] Pierwszy pełny przejazd od startu do mety.

## Kryterium ukończenia

Całą trasę można przejechać bez przerwania, błędu pozycji lub opuszczenia drogi.

---

# Etap 4 — technika pokonywania zakrętów

**Planowany czas:** tydzień 5–7

## Cel

Wprowadzić autorską mechanikę oceniającą odpuszczenie i ponowne rozpoczęcie pedałowania.

## Zadania

- [ ] Obliczanie krzywizny drogi.
- [ ] Określenie strefy wejścia, apeksu i wyjścia.
- [ ] Obliczanie zalecanej prędkości.
- [ ] Analiza momentu zmniejszenia mocy.
- [ ] Analiza momentu wznowienia pedałowania.
- [ ] Automatyczny wybór toru przejazdu.
- [ ] Poszerzenie toru po błędzie.
- [ ] Utrata prędkości po błędzie.
- [ ] Kontrolowany uślizg bez upadku.
- [ ] Wpływ mokrej nawierzchni.
- [ ] Ocena każdego zakrętu.
- [ ] Regulowane poziomy asysty.
- [ ] Testy powtarzalności wyników.

## Kryterium ukończenia

Różne decyzje dotyczące mocy i kadencji dają widocznie różne, ale powtarzalne rezultaty przejazdu zakrętu.

---

# Etap 5 — HUD i przebieg sesji

**Planowany czas:** tydzień 6–8

## Zadania

- [ ] Ekran konfiguracji jazdy.
- [ ] Ustawienia masy, CdA i Crr.
- [ ] Wybór poziomu asysty.
- [ ] Moc i kadencja.
- [ ] Prędkość.
- [ ] Nachylenie.
- [ ] Czas i dystans.
- [ ] Pozostały dystans.
- [ ] Profil wysokości.
- [ ] Pozycja na profilu.
- [ ] Informacje o nadchodzącym zakręcie.
- [ ] Ocena przejazdu zakrętu.
- [ ] Ekran mety i podsumowania.
- [ ] Możliwość ograniczenia lub ukrycia HUD-u.

## Kryterium ukończenia

Użytkownik może rozpocząć, ukończyć i podsumować całą sesję bez korzystania z narzędzi deweloperskich.

---

# Etap 6 — kamery, kolarz i rower

**Planowany czas:** tydzień 7–9

## Zadania

- [ ] Jeden model roweru.
- [ ] Jeden model kolarza.
- [ ] Dopasowanie kolarza do roweru.
- [ ] Animacja pedałowania zależna od kadencji.
- [ ] Toczenie bez pedałowania.
- [ ] Pochylenie w zakrętach.
- [ ] Kamera za kolarzem.
- [ ] Kamera z perspektywy kierownicy.
- [ ] Przełączanie kamer podczas jazdy.
- [ ] Stabilizacja kamer na nierównościach i zakrętach.

## Kryterium ukończenia

Ruch kolarza, roweru i kamer jest płynny i zgodny z parametrami jazdy.

---

# Etap 7 — świat i oprawa wizualna

**Planowany czas:** tydzień 8–11

## Zadania

- [ ] Podział świata na dolinę, las i wysokie góry.
- [ ] Materiały drogi i mokrej nawierzchni.
- [ ] Roślinność.
- [ ] Skały i teren wysokogórski.
- [ ] Mała miejscowość.
- [ ] Punkty charakterystyczne trasy.
- [ ] Życie w kilku przygotowanych lokalizacjach.
- [ ] System LOD, Nanite lub instancjonowania zależnie od assetu.
- [ ] Kontrola gęstości obiektów.
- [ ] Profile jakości grafiki.
- [ ] Testy 1080p/60 FPS na RTX 2070 Super.

## Kryterium ukończenia

Świat ma spójny alpejski charakter, a pełna trasa utrzymuje założony budżet wydajności.

---

# Etap 8 — dynamiczna pogoda i dźwięk

**Planowany czas:** tydzień 9–11

## Zadania

- [ ] Zaplanowany przebieg pogody.
- [ ] Opcjonalny tryb losowy.
- [ ] Zapisywane ziarno losowości.
- [ ] Wiatr wpływający na fizykę.
- [ ] Deszcz i moknięcie nawierzchni.
- [ ] Wpływ mokrej drogi na fizykę zakrętów.
- [ ] Dźwięki napędu i wolnobiegu.
- [ ] Dźwięki opon i hamowania.
- [ ] Wiatr zależny od prędkości i kierunku.
- [ ] Dźwięki deszczu, lasu, zwierząt i miejscowości.
- [ ] Testy wydajności podczas najcięższych warunków.

## Kryterium ukończenia

Pogoda zmienia wygląd, dźwięk i fizykę, nie powodując niedopuszczalnych spadków płynności.

---

# Etap 9 — zapis sesji i eksport FIT

**Planowany czas:** tydzień 11–12

## Zadania

- [ ] Lokalny format zapisu sesji.
- [ ] Historia przejazdów.
- [ ] Automatyczne zabezpieczenie danych podczas jazdy.
- [ ] Podsumowanie zakrętów.
- [ ] Generowanie pliku FIT.
- [ ] Walidacja wygenerowanego pliku.
- [ ] Test importu FIT do co najmniej jednej zewnętrznej usługi.
- [ ] Obsługa błędu zapisu.

## Kryterium ukończenia

Ukończona aktywność jest dostępna lokalnie i może zostać wyeksportowana jako poprawny plik FIT.

---

# Etap 10 — stabilizacja MVP

**Planowany czas:** od tygodnia 12

## Zadania

- [ ] Pełny test trasy od startu do mety.
- [ ] Test różnych poziomów mocy.
- [ ] Test wszystkich poziomów asysty.
- [ ] Test suchej i mokrej nawierzchni.
- [ ] Test obu kamer.
- [ ] Test zapisu i eksportu FIT.
- [ ] Profilowanie CPU, GPU i pamięci.
- [ ] Usunięcie błędów blokujących.
- [ ] Przygotowanie wersji Windows.
- [ ] Instrukcja instalacji i uruchomienia.
- [ ] Oznaczenie wydania `v0.1.0-mvp`.

## Kryterium ukończenia

Spełnione są wszystkie kryteria z dokumentu PRODUCT_REQUIREMENTS.md, a aplikację można uruchomić na innym komputerze z Windows bez środowiska programistycznego.

---

# Po MVP

Kolejność orientacyjna:

1. Obsługa BLE/FTMS i pierwszego prawdziwego trenażera.
2. Sterowanie oporem.
3. Integracja ze Stravą.
4. Import i generowanie kolejnych tras.
5. Treningi strukturalne.
6. Ghost i porównywanie przejazdów.
7. Multiplayer.
8. Drafting i fizyka grupy.
9. Kolejne platformy treningowe.
10. Inne systemy operacyjne.
