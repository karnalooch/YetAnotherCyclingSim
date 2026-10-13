Jasne 😄 **Poniżej cały plan. Niczego z niego nie wykonałem — odczytałem pliki, stan GitHub i istniejące dane. P0–P4 wypadają z dalszych prac.**

Proponuję dojść najpierw do **jednej małej, sensownie widocznej grupy skał w aktualnym świecie**, następnie sprawdzić jej odtwarzanie i dopiero rozszerzać zasiew. Plan obejmuje całą mapę **2016,5 × 2016,5 m**, ale ilość geometrii wynika z potrzeb obrazu. Przegląd szarych obszarów zostaje odłożony do wspólnej sesji i nie blokuje tej ścieżki.

**Punkt wyjścia, który zweryfikowałem**

| Element | Rzeczywisty status |
|---|---|
| Fundament drogi i poboczy | #364 ukończone; punktem odniesienia jest v0.3.1 |
| Aktualna praca | `D:/yacs/work/pcg365-contact-remote`, lokalna gałąź `codex/365-rock-contact-remote` |
| Opublikowany kod | `c210fdbed734690ffe638a7210177459751a9475`; [PR #474](https://github.com/karnalooch/YetAnotherCyclingSim/pull/474) nadal Draft |
| Nowa mapa i analiza widoczności | **Lokalny, niezacommitowany kandydat.** Sprawdziłem zgodność archiwum tablic i ich skrótów z manifestem |
| Cztery uproszczone skały | Przygotowane źródła i stage importu; **brak pełnej kwalifikacji nowych wariantów w docelowym terenie** |
| Ostatni zapisany stan próby Remote | Anulowanie i pełny rollback, `preview_placed: 0`; nie wykonywałem nowej kontroli obrazu Remote |
| Regionalny zasiew | **Wymaga implementacji** — obecny przepis jest ograniczony do historycznych punktów |
| Szare uproszczenia | Decyzja o charakterze opracowania jest znana; konkretne powierzchnie **wymagają wspólnego obejrzenia** |
| Wydajność | `DEFERRED_AFTER_M3`, `performance_pass: false` |

Podstawą przestrzenną jest wskazana [aktualna mapa](D:/yacs/work/pcg365-contact-remote/docs/experiments/sa-calobra-spatial-treatment-plan-20261013/spatial-plan.html). Jej kolory wyznaczają propozycje opracowania, a nie gotowe obszary do wypełnienia meshami.

**Pierwszy obszar: mały fragment przy oknie 0067**

Zamiast wybierać miejsce na oko, porównałem istniejące dane nachylenia, pełnych wykluczeń i widoczności. Najbardziej obiecujący pierwszy obszar poszukiwania znalazłem przy [oknie 0067](D:/yacs/work/pcg365-contact-remote/docs/experiments/sa-calobra-tpp-survey-20261008/windows/window-0067.md):

- Zakres środków znalezionych komórek: **X 1128,5–1135,5 m, Y 1162,0–1173,5 m**, w lokalnym układzie mapy: X na wschód, Y na południe.
- W tym skupisku znalazłem **137 komórek źródłowych** spełniających wstępny filtr: łagodne sąsiedztwo, brak zapisanych wykluczeń i odpowiednia widoczność pola planistycznego.
- Przykładowy punkt wyszukiwania: **X 1129,5 m, Y 1164,5 m**. W jego źródłowym sąsiedztwie 7 × 7 pikseli maksymalne nachylenie wynosi około **9,65°**, a dolna granica odległości od wykluczeń około **3,29 m**.
- Odpowiadające pole planistyczne ma **15 trafień kamer**, maksymalnie około **40,6 px/m** i najbliższą próbkowaną odległość **23 m**.

To **kandydat do sprawdzenia, nie zatwierdzony wielokąt zasiewu**. Widoczność dotyczy pola 4 m, a nachylenie pochodzi z danych źródłowych. Nie dowodzi to kontaktu z aktualną powierzchnią UE ani zasadności skał w tym miejscu. Mapa klasyfikuje ten fragment jako „material-first”, więc dodanie kilku skał musi mieć uzasadnienie w rzeczywistym obrazie.

Wybieram go jako pierwszy, ponieważ daje szansę na czytelny efekt przy małej powierzchni i bez rozpoczynania od trudnego, stromego piargu. **Najkrótszy brakujący krok to identyfikacja tej konkretnej powierzchni w aktualnym Remote.**

1. **Ustalić jeden aktualny pakiet wejściowy**

   **Cel:** kolejne prace mają korzystać z tej samej mapy, skał i wersji świata.

   **Wejścia:** lokalne zmiany analizy widoczności, `visibility-plan.json`, `visibility-arrays.npz`, atlas powierzchni, cztery uproszczone modele oraz checkpoint v0.3.1.

   **Warunek rozpoczęcia:** wznowienie implementacji przez właściciela. Ten dokument pozostaje wyłącznie planem.

   **Późniejsze działanie:** przejrzeć lokalny diff, utrwalić aktualne decyzje i opublikować spójny checkpoint na istniejącej gałęzi. Uaktualnić opis PR: obecnie opisuje starszy widok wykluczeń. Osobno zapisać SHA kodu, skróty danych i rzeczywiście zainstalowaną wersję przepisu UE.

   **Koniec etapu:** istnieje jednoznaczny zestaw wejść do pierwszej partii; lokalne wyniki nie są przedstawiane jako opublikowana lub native sprawdzona wersja.

   **Kontrola i rollback:** zachować oryginalne rastry, wcześniejszą mapę i checkpoint świata. Ten etap nie zmienia sceny.

2. **Zarejestrować pierwszą rzeczywistą powierzchnię przy oknie 0067**

   **Cel:** zamienić wskazanie z mapy na niewielki, rozpoznany fragment aktualnego świata.

   **Wejścia:** podany wyżej obszar poszukiwania, zapisane kamery okna 0067, oryginalne wykluczenia 0,5 m i aktualna scena v0.3.1.

   **Warunek rozpoczęcia:** spójny pakiet z etapu 1 oraz dostęp do oglądania właściwej sceny.

   **Późniejsze działanie:** obejrzeć fragment w Remote z bliska i z kierunków jazdy. Ustalić, czy widoczną powierzchnią jest Landscape, istniejący mesh, BOB czy inna konstrukcja. Wyznaczyć niewielki rzeczywisty obrys i nadać mu `surface_id`. Sprawdzić, czy luźne skały poprawią obraz.

   Obecny `focus_road` nie wystarcza do wygodnego powrotu w każde miejsce. Najmniejszym potrzebnym usprawnieniem jest **zapisany, sprawdzony punkt kamery dla tego obszaru**, z odczytem położenia. Jeśli potrzebuje obsługi programowej, należy dodać ograniczony przepis do istniejącego Remote. Nie potrzeba nowego systemu sterowania. Nie obchodzimy wcześniejszej blokady dostępu przeglądarki przez CDP ani helpery.

   **Koniec etapu:** mamy powierzchnię, jej właściciela, obrys i widoki kontrolne. Jeśli aktualna geometria lub charakter miejsca wyklucza skały, wybieramy następny kandydat z danych; nie dopasowujemy terenu do modelu.

   **Kontrola i rollback:** na tym etapie tylko oglądanie i rejestracja. Brak zmian w geometrii.

3. **Przygotować ograniczony zasiew dla nowego obszaru**

   **Cel:** umożliwić pierwszą partię poza historycznymi punktami, zachowując istniejące zabezpieczenia.

   **Wejścia:** zarejestrowana powierzchnia, jej obrys, aktualne wykluczenia i konkretne warianty skał.

   **Warunek rozpoczęcia:** etap 2 potwierdził odpowiednie miejsce i podłoże.

   **Późniejsze działanie:** rozszerzyć obecny przepis o wersjonowany manifest jednej powierzchni: jej identyfikator, dopuszczony obrys, źródła, listę assetów, deterministyczne pozycje i limit liczby obiektów. Zachować uwierzytelnienie, kolejkę, licznik postępu, anulowanie oraz usuwanie wyłącznie obiektów własnej partii.

   Pierwszy wariant powinien obsługiwać **jedną powierzchnię i najwyżej pięć pozycji w żądaniu**. To proponowane ograniczenie pierwszej próby, nie budżet wydajności całego świata.

   **Koniec etapu:** przepis odrzuca pozycje poza obrysem, błędne źródła, przekroczenie limitu i konflikt pełnego obrysu skały z wykluczeniami. Anulowanie usuwa całą własną partię.

   **Kontrola i rollback:** testy granic obszaru, zmiany manifestu, kolizji obrysów, anulowania i ponowienia żądania. Dotychczasowy przepis pozostaje identyfikowalny jako historyczny; nie zmieniamy znaczenia jego wcześniejszych dowodów.

4. **Dopasować pierwsze skały bez zmieniania terenu**

   **Cel:** uzyskać poprawny kontakt nowych modeli z wybraną powierzchnią.

   **Wejścia i kolejność assetów:**

   | Wariant | Trójkąty | Proponowana rola |
   |---|---:|---|
   | N06 | 3388 | Pierwszy test kontaktu; niewielki obrys |
   | N05 | 3168 | Drugi kształt do małej grupy |
   | N03 | 5640 | Większy akcent, dopiero gdy miejsce go uzasadnia |
   | N04 | 6320 | Alternatywny większy akcent |

   **Warunek rozpoczęcia:** działający ograniczony przepis oraz potwierdzone podłoże. Obecny pomiar obsługuje Landscape; trafienie w BOB lub mesh wymaga właściwego kontraktu kontaktu, a nie podmiany etykiety powierzchni.

   **Późniejsze działanie:** sprawdzić native wymiary, pivot, liczbę trójkątów, materiał i kolizję. Następnie dopasować N06 na rzeczywistej pozycji w pierwszym obszarze. Zachować dotychczasowe **10° nachylenia, 20% zagłębienia, wymagania ekspozycji i refinację 65/129**. Początkowo pozostawić już obsługiwane ustawienie skali i orientacji; późniejsze obroty wymagają ponownego sprawdzenia obrysu i kontaktu.

   **Koniec etapu:** co najmniej jeden nowy wariant ma poprawny odczyt native i przekonujący kontakt w aktualnym Remote. Wynik jest przypisany do konkretnego assetu, ustawienia i powierzchni. Próbkowany kontakt nadal nie oznacza dowodu ciągłego podparcia całej bryły.

   **Kontrola i rollback:** nieudane ustawienie usunąć. Gdy potrzebne jest nadmierne zakopanie albo pojawia się szczelina, zmienić asset lub pozycję w dopuszczonym obszarze. Nie poluzowywać limitów na podstawie samej porażki.

5. **Dowieźć pierwszą małą grupę jako użyteczny efekt**

   **Cel:** zobaczyć fragment świata, który rzeczywiście wygląda lepiej.

   **Warunek rozpoczęcia:** pozytywna kwalifikacja kontaktu z etapu 4.

   **Późniejsze działanie:** zacząć od **trzech skał**, następnie — jeśli kompozycja tego potrzebuje — dojść do **pięciu**. Użyć jednego lub dwóch zakwalifikowanych wariantów. Zachować przerwy i widoczne podłoże. Większy N03/N04 dodawać tylko tam, gdzie jego sylwetka ma znaczenie.

   Obejrzeć w Remote kontakt, skalę, powtarzalność, zasłanianie drogi oraz wygląd z obu kierunków. Nie produkować osobnej galerii renderów.

   **Koniec etapu:** jedna mała grupa ma sens z kamery jazdy, nie narusza wykluczeń, daje się usunąć i odtworzyć z tych samych wejść.

   **Kontrola i rollback:** każda partia ma własną tożsamość i listę obiektów. Wycofanie przywraca poprzednią scenę bez naruszania drogi, materiałów i terenu.

   **Koszt kontroli:** na pierwszą partię zachować istniejące pełne zabezpieczenia geometrii. Zorganizować sprawdzanie wszystkich jej skał we wspólnej transakcji, aby nie powtarzać dwóch skanów około **2,9 mln identyfikatorów trójkątów** osobno dla każdego kamienia. Istniejący licznik pokazuje postęp; zakończenie obliczeń nie jest automatyczną akceptacją.

6. **Utrwalić działający fragment i domknąć mechanikę #365**

   **Cel:** przejść od tymczasowej grupy do powtarzalnego generowania.

   **Wejścia:** zakwalifikowane assety, powierzchnia, sprawdzone pozycje i istniejące elementy grafu PCG.

   **Warunek rozpoczęcia:** pierwsza grupa działa i jej rezultat jest wart zachowania.

   **Późniejsze działanie:** podłączyć dopuszczone dane do istniejącego grafu i standardowego spawnera. Tożsamość instancji powiązać z powierzchnią i stabilnym punktem źródłowym; zmiana sąsiedniej partii nie powinna przetasowywać całego zasiewu. Sprawdzić generowanie, czyszczenie, ponowne generowanie oraz lokalną zmianę maski.

   Powtarzane modele grupować w instancje według mesha, materiału i obszaru. UE udostępnia ISM właśnie do takich powtórzeń; dobór ISM/HISM i ich ustawień wymaga sprawdzenia na docelowej scenie. [Dokumentacja Epic UE 5.8](https://dev.epicgames.com/documentation/en-us/unreal-engine/instanced-static-mesh-component-in-unreal-engine).

   PCGEx włączać do konkretnej operacji dopiero wtedy, gdy jest potrzebny i ma potwierdzoną zgodność. Pierwsza użyteczna grupa nie powinna czekać na rozbudowę biblioteki węzłów.

   **Koniec etapu:** zgodne identyfikatory, liczba, transformacje i materiały po regeneracji oraz po świeżym odczycie zapisanego pochodnego konsumenta. Trwały zapis obejmuje tylko zatwierdzone nowe wyjście.

   **Kontrola i rollback:** osobny checkpoint pochodnego świata i jawna lista pakietów. Świeży odczyt zaplanować w bezpiecznym oknie własności hosta; nie przerywać otwartego edytora właściciela. Dowód zapisu nie zastępuje dowodu ponownego wczytania.

7. **Rozszerzać świat czterema odrębnymi sposobami**

   Każdy kolejny fragment przechodzi tę samą krótką ścieżkę: **potrzeba w obrazie → powierzchnia i wykluczenia → mała partia → kontakt i oglądanie → regeneracja**.

   | Rodzaj pracy | Co konkretnie robić | Warunek i kryterium zakończenia |
   |---|---|---|
   | **Bliskie luźne kamienie** | Powtarzać sprawdzoną metodę na małych, widocznych powierzchniach; korzystać głównie z N05/N06, większych form używać oszczędnie | Pełny obrys, kontakt, droga i brak wzoru „dywanu”; każdy fragment odtwarzalny |
   | **Strome piargi** | Rozdzielić materiał drobnego rumoszu, nieliczne większe kamienie i ewentualne dopasowane skupiska | Selekcja 24–42° nie pasuje do obecnego kontaktu 10°. Potrzebna osobna kwalifikacja sposobu osadzenia; nie rozszerzenie limitu „żeby przeszło” |
   | **Pionowe ściany i duże formy** | Najpierw sprawdzić istniejące meshe. Poprawiać tylko brakującą czytelną bryłę, półkę, krawędź lub sylwetkę | Jedna powierzchnia ma jednego właściciela. Skały N03/N04 nie są automatycznie modułami klifu. Lokalna naprawa wymaga własnego zakresu, delty i rollbacku |
   | **Materiały** | Zachować zaakceptowaną bazę; używać istniejącego Material Forge do skali wapienia, normalnych i drobnej struktury | Materiał poprawia powierzchnię przy poprawnej geometrii; nie maskuje szczelin i wad kontaktu |
   | **Szare „Obiekty uproszczone”** | Po wspólnej sesji wybierać potrzebne duże formy i ograniczony detal; część powierzchni może pozostać bez nowych obiektów | Oceniona sylwetka, bliższe podejścia i istotne cienie. Brak trafień kamer nie oznacza niewidoczności |

   Dla pionowych form dobrym początkiem późniejszego przeglądu są istniejące karty okien **0103** i **0181**: pierwsze dotyczy bliskiej ściany, drugie dominującego masywu. To punkty orientacyjne przeglądu, nie gotowe granice meshy.

   Szare regiony zachowują swoją kolejkę ośmiu obszarów. Ich odroczenie blokuje decyzje dotyczące tych powierzchni, **nie pierwszą grupę ani pozostałe rozpoznane fragmenty**.

8. **Rozwiązać różnicę między mapą a wykluczeniami konsumenta**

   **Cel:** mapa i generator mają mówić uczciwie o tym, co wolno zrobić.

   **Stan obecny:** widok pokazuje dokładne drogi i cieki z istniejącym buforem wodnym. Techniczne maski nadal obejmują również pozostałe ograniczenia. Dodatkowe **161 342 m²** zostało przeanalizowane planistycznie, ale nie dopuszczone do zasiewu.

   **Późniejsze działanie:** dla pierwszego fragmentu użyć pełnych aktualnych wykluczeń. Dzięki temu pierwszy efekt nie wymaga rozwiązywania wszystkich prostokątów BOB.

   Następnie rozpatrywać przeszkadzające holdbacki lokalnie: ustalić rzeczywisty zasięg BOB, pobocza, budynku lub infrastruktury. Jeśli stary prostokąt jest zbyt szeroki, przygotować źródłowo uzasadnioną pochodną maskę dla tego fragmentu, z porównaniem przed/po i kontrolą native. Zachować ochronę rzeczywistych obiektów i pełnego obrysu skały.

   **Koniec etapu:** każda zmiana dopuszczenia ma przyczynę, zakres, źródło i dowód; ukrycie warstwy w HTML nigdy nie zmienia zasad generatora.

   **Kontrola i rollback:** wersjonowane maski i odtworzenie poprzedniej wersji. Nie usuwać zbiorczo bitów BOB, budynków i infrastruktury.

9. **Publikować małymi partiami i zachować właściwe bramki**

   **Cel:** postęp jest dostępny w Remote i ma dowody przypisane do rzeczywistej wersji.

   Po każdej sensownej zmianie: przegląd diffu, odpowiednie testy kontaktu/wykluczeń/deterministyczności, dokumentacja oraz guards links/i18n/structure/freshness. Potem publikacja na dokładnym SHA i wymagane CI. Instalacja przepisu, aktualizacja strony Remote i stan świata mają osobne wersje oraz dowody.

   Ciężkie dowody prowadzić przez istniejący **Gumball Proof Broker**, zgodnie z dostępną allowlistą i zasadami ponownego użycia. Publisher Remote pozostaje istniejącą ścieżką wdrożenia; nie należy przedstawiać go jako dowodu kwalifikacji świata. Brakującego rodzaju dowodu nie zastępujemy nowym „systemem PASS”.

   Po publikacji sprawdzić rzeczywisty odczyt assetów i instancji oraz świeży obraz w Remote. Wymóg świeżo wczytanego, wyrenderowanego konsumenta pozostaje; sposób jego udokumentowania przez istniejącą ścieżkę live musi zachować wymagane dowody. Nie planuję osobnych sesji renderowania galerii.

   **Zależności:** #365 prowadzi do [#366 — korytarza bezpieczeństwa](https://github.com/karnalooch/YetAnotherCyclingSim/issues/366), potem [#367 — biomów](https://github.com/karnalooch/YetAnotherCyclingSim/issues/367) i produkcyjnego [#368 — skał, klifów i piargów](https://github.com/karnalooch/YetAnotherCyclingSim/issues/368). #368 ma ograniczony wcześniejszy wyjątek dla diagnostyki klifów; nie jest to zgoda na pełny regionalny rollout. Pierwsza próba w #365 nie zamyka tych etapów.

   **Koniec etapu:** opublikowany kandydat ma wymagane dowody dla swojego zakresu. Draft, lokalny wynik, native sprawdzenie, odbiór wizualny i merge pozostają odrębnymi stanami.

**Ograniczanie kosztu od pierwszej partii**

Stosowałbym cztery przygotowane źródła, współdzielone materiały i instancje pogrupowane przestrzennie. Drobne pory, pęknięcia i żwir przenosiłbym do materiału; geometrię zostawiał tam, gdzie zmienia widoczną formę. Odległości zanikania oraz LOD dobierałbym po obejrzeniu przejść, z zachowaniem ważnych sylwetek.

Rejestrowałbym liczbę instancji, użyte meshe, materiały, kolizje i koszt przygotowania partii. **Mniej trójkątów nie jest jeszcze zmierzonym przyspieszeniem.** Nie ustalam tu nowego budżetu FPS ani liczby skał dla całej mapy.

Optymalizację pełnego skanowania geometrii zostawiłbym dopiero na moment, gdy rzeczywiście utrudnia kolejne partie. Wtedy lokalizacja kontroli wymaga dowodu, że pomijane obiekty nie mogą przecinać sprawdzanego obszaru, oraz zachowania wykrywania zmian. Samo skrócenie listy sprawdzanych meshów byłoby osłabieniem dowodu.

**Kolejność do wykonania po wznowieniu:** utrwalić aktualną mapę → rozpoznać fragment przy oknie 0067 → dodać ograniczoną obsługę tego obszaru → dopasować N06/N05 → pokazać grupę 3–5 skał w Remote → sprawdzić odtwarzanie → rozszerzać na kolejne rozpoznane powierzchnie. To daje pierwszy widoczny rezultat bez czekania na szare regiony, pełne klify czy przebudowę infrastruktury.