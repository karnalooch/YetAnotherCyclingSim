# YetAnotherCyclingSim — wymagania produktu

**Wersja dokumentu:** 0.1  
**Status:** Draft  
**Platforma pierwszego wydania:** Windows  
**Sillish:** Unreal Engine 5  
**Model produkcji:** projekt jednoosobowy wspomagany przez AI

## 1. Wizja produktu

YetAnotherCyclingSim to realistyczny symulator kolarstwa halowego, łączący:

- wiarygodną fizykę jazdy;
- piękne i realistyczne światy 3D;
- zaawansowaną technikę pokonywania zakrętów;
- obsługę trenażerów rowerowych;
- realistyczne trasy inspirowane prawdziwymi miejscami;
- możliwość późniejszej rozbudowy o multiplayer.

Docelową przewagą produktu ma być połączenie realizmu wizualnego, fizyki, pogody oraz techniki jazdy.

## 2. Cel MVP

Pierwsze pełne MVP umożliwia ukończenie swobodnej jazdy po jednej fikcyjnej trasie inspirowanej Alpami.

Jazda powinna trwać około 20–30 minut i prowadzić od startu do mety bez powtarzania fragmentów trasy.

## 3. Pierwsza trasa

Trasa powinna:

- być fikcyjna, ale wiarygodna geograficznie;
- być inspirowana krajobrazem alpejskim;
- mieć pofałdowany profil z podjazdami i zjazdami;
- zawierać zakręty o różnej trudności;
- prowadzić przez trzy główne strefy:
  1. zieloną dolinę i niewielką miejscowość;
  2. gęsty las;
  3. surowy teren wysokogórski;
- nie wykorzystywać widocznie powtarzających się fragmentów;
- zawierać kilka starannie przygotowanych, ożywionych miejsc;
- poza kluczowymi punktami koncentrować się na naturze i krajobrazie.

## 4. Sterowanie MVP

Pierwsza wersja będzie testowana bez fizycznego trenażera.

Moc i kadencja będą sterowane za pomocą:

- klawiatury;
- suwaków interfejsu diagnostycznego.

Architektura wejścia musi pozwalać później zastąpić sterowanie testowe danymi BLE/FTMS bez zmiany silnika fizycznego.

## 5. Model fizyczny

Model powinien uwzględniać co najmniej:

- masę kolarza;
- masę roweru;
- moc kolarza;
- kadencję;
- nachylenie drogi;
- grawitację;
- opór toczenia Crr;
- opór aerodynamiczny CdA;
- gęstość powietrza;
- kierunek i prędkość wiatru;
- toczenie bez pedałowania;
- rozpędzanie i utratę prędkości;
- wpływ mokrej nawierzchni.

Obliczenia fizyczne nie mogą zależeć od liczby klatek obrazu.

Użytkownik otrzyma wartości domyślne i presety. Pełne parametry fizyczne będą dostępne w ustawieniach zaawansowanych.

## 6. Technika pokonywania zakrętów

Użytkownik nie steruje bezpośrednio kierownicą ani hamulcami.

Na wynik przejazdu zakrętu wpływają:

- prędkość wejściowa;
- moment zmniejszenia lub odpuszczenia mocy;
- zmiana kadencji;
- moment ponownego rozpoczęcia pedałowania;
- promień i profil zakrętu;
- nachylenie drogi;
- stan nawierzchni;
- przyczepność;
- wiatr.

System automatycznie wyznacza tor przejazdu.

Błędna technika może powodować:

- poszerzenie toru;
- wolniejszą linię przejazdu;
- uślizg;
- dużą utratę prędkości na wyjściu;
- stratę czasu;
- obniżenie oceny techniki.

Upadki nie należą do MVP. Zostaną rozważone w późniejszej wersji.

## 7. System asyst

Poziom pomocy przy pokonywaniu zakrętów będzie regulowany.

Planowane poziomy:

1. Same ostrzeżenia.
2. Podpowiedź momentu odpuszczenia mocy.
3. Łagodna korekta toru lub prędkości.
4. Pełne automatyczne zapobieganie poważnemu błędowi.

System powinien nagradzać płynność, a nie tylko karać błędy.

Każdy zakręt powinien otrzymać ocenę uwzględniającą:

- wejście;
- moment odpuszczenia;
- przejazd przez apex;
- moment ponownego przyspieszenia;
- prędkość wyjściową;
- całkowitą stratę lub zysk czasu.

## 8. Kamera

MVP udostępnia dwa przełączane widoki:

- kamera za kolarzem;
- kamera z perspektywy kolarza lub kierownicy.

Oba widoki muszą pozostać czytelne podczas podjazdów, zjazdów, zakrętów i opadów.

## 9. Kolarz i rower

MVP zawiera:

- jednego dopracowanego kolarza;
- jeden dopracowany rower;
- animację pedałowania zależną od kadencji;
- pochylenie kolarza i roweru w zakrętach;
- zmianę pozycji zależną od sytuacji na trasie;
- animację toczenia bez pedałowania.

Kreator postaci, wybór wielu rowerów i katalog wyposażenia nie należą do MVP.

## 10. Pogoda

MVP zawiera dynamiczną pogodę.

Dostępne tryby:

- zaplanowana sekwencja pogodowa powiązana z trasą;
- opcjonalny przebieg losowy.

Pogoda wpływa na:

- wygląd świata;
- oświetlenie;
- dźwięk;
- widoczność;
- kierunek i siłę wiatru;
- opór aerodynamiczny;
- mokrość nawierzchni;
- opór toczenia;
- przyczepność.

Losowa pogoda powinna korzystać z możliwego do zapisania ziarna losowości, aby umożliwić powtarzalne testy.

## 11. HUD

Podczas jazdy stale dostępne są:

- moc;
- kadencja;
- prędkość;
- aktualne nachylenie;
- przejechany dystans;
- pozostały dystans;
- czas jazdy;
- profil wysokości;
- pozycja użytkownika na profilu.

HUD powinien być czytelny, skalowalny i możliwy do ograniczenia lub ukrycia.

Podczas zbliżania się do zakrętu może dodatkowo pokazywać:

- trudność zakrętu;
- zalecaną prędkość;
- sugerowany moment odpuszczenia;
- aktualny poziom asysty.

## 12. Dźwięk

MVP zawiera przestrzenne dźwięki:

- napędu;
- wolnobiegu;
- opon;
- hamowania;
- wiatru zależnego od prędkości i kierunku;
- deszczu;
- lasu;
- zwierząt;
- miejscowości.

Muzyka oraz oddech kolarza nie należą obecnie do MVP.

## 13. Dane przejazdu

Po ukończeniu jazdy aplikacja:

- zapisuje pełne dane sesji lokalnie;
- dodaje przejazd do lokalnej historii;
- pokazuje podsumowanie;
- pokazuje ocenę zakrętów;
- umożliwia eksport pliku FIT.

Automatyczna synchronizacja ze Stravą nie należy do MVP.

## 14. Wydajność

Podstawowy cel wydajnościowy:

- rozdzielczość 1920 × 1080;
- stabilne 60 FPS;
- komputer referencyjny:
  - Intel Core i5 10. generacji;
  - 32 GB RAM DDR4;
  - NVIDIA RTX 2070 Super;
- możliwość wyboru jakości grafiki;
- brak zależności fizyki od chwilowych spadków FPS.

Płynność ma pierwszeństwo przed ustawieniem wszystkich efektów UE5 na najwyższy poziom.

## 15. Platformy

Pierwsze wydanie:

- Windows 10/11.

Późniejsze wersje mogą obsługiwać inne systemy, dlatego logika fizyczna i formaty danych nie powinny być niepotrzebnie związane z Windows.

## 16. Organizacja projektu

- Prywatne repozytorium GitHub.
- Git LFS dla dużych plików binarnych.
- Kod i nazwy techniczne w języku angielskim.
- Dokumentacja projektu w języku polskim.
- Unreal Engine uruchamiany na komputerze domowym.
- Komputer w pracy używany do dokumentacji, Git, lekkiego kodu i przygotowywania danych.
- Projekt tworzony przez jedną osobę z pomocą narzędzi AI.
- Dostępny czas: 11–20 godzin tygodniowo.
- Początkowy budżet na narzędzia i assety: do 500 zł.

## 17. Poza zakresem MVP

Do MVP nie należą:

- multiplayer;
- obsługa prawdziwego trenażera;
- BLE/FTMS i ANT+;
- treningi ERG;
- integracja ze Stravą;
- Garmin Connect;
- TrainingPeaks;
- Xert;
- Intervals.icu;
- Wahoo Cloud;
- wiele tras;
- import dowolnego GPX;
- kreator postaci;
- wiele rowerów;
- sklep i system odblokowywania sprzętu;
- pełny ruch drogowy;
- upadki;
- cykl dnia i nocy;
- realistyczne odwzorowanie konkretnej prawdziwej trasy;
- multiplayer i drafting grupowy.

## 18. Kryterium ukończenia MVP

MVP jest ukończone, gdy użytkownik może:

1. Uruchomić aplikację na Windows.
2. Ustawić parametry kolarza i roweru.
3. Wybrać poziom asysty oraz tryb pogody.
4. Rozpocząć jazdę.
5. Sterować mocą i kadencją bez trenażera.
6. Przejechać całą trasę od startu do mety.
7. Doświadczyć podjazdów, zjazdów, zakrętów i dynamicznej pogody.
8. Otrzymać ocenę techniki zakrętów.
9. Zachować około 60 FPS w 1080p na komputerze referencyjnym.
10. Zapisać przejazd lokalnie.
11. Wyeksportować aktywność do pliku FIT.

## 19. Główne ryzyko

Pełny zakres MVP jest bardzo ambitny dla jednej początkującej osoby i nie jest realistyczny do ukończenia w 2–3 miesiące bez istotnego ograniczenia jakości lub funkcji.

Termin 2–3 miesięcy należy traktować jako termin pierwszego działającego kamienia milowego. Szczegółowy harmonogram zostanie przygotowany po rozbiciu MVP na wersje pośrednie.

## 20. Pack Dynamics i automatyczne prowadzenie w grupie (po MVP)

Pack Dynamics jest funkcją planowaną po ukończeniu stabilnego single-player MVP i nie rozszerza bieżącego zakresu MVP.

### Sterowanie i intencja użytkownika

Użytkownik nie ma fizycznej możliwości bezpośredniego sterowania rowerem w lewo ani w prawo. Podstawowym wejściem pozostają moc i kadencja. System interpretuje wynikającą z nich docelową prędkość i przyspieszenie jako sygnał intencji jazdy, natomiast samodzielnie wybiera bezpieczny tor w obrębie drogi.

Gracz nie wybiera strony wyprzedzania, nie ustawia ręcznie pozycji w cieniu aerodynamicznym i nie wykonuje ręcznych korekt bocznych w peletonie.

### Zasady pozycjonowania bocznego

Zmiana pozycji bocznej nie może być arbitralnym przesunięciem modelu. Każdy manewr boczny musi mieć jawny powód, np.:

- `FOLLOW_WHEEL`;
- `OVERTAKE_LEFT`;
- `OVERTAKE_RIGHT`;
- `AVOID_COLLISION`;
- `RETURN_TO_LINE`;
- `CORNER_POSITION`;
- `CROSSWIND_POSITION`.

Przy braku uzasadnionego `LateralIntent` zawodnik powinien utrzymywać stabilną linię zamiast stale przemieszczać się w lewo i w prawo.

System powinien stosować histerezę i czas zobowiązania do rozpoczętego manewru. Po wybraniu strony wyprzedzania nie wolno zmieniać decyzji co klatkę tylko dlatego, że chwilowo druga strona otrzymała nieznacznie lepszą ocenę. Zmiana planu jest dopuszczalna, gdy pojawi się realne zagrożenie lub wybrana luka przestanie być dostępna.

### Unikanie kolizji i brak przenikania modeli

Kolizjom należy zapobiegać predykcyjnie, zanim modele się zetkną. System powinien analizować względną prędkość, przewidywaną pozycję i czas do potencjalnego konfliktu.

Każdy zawodnik powinien mieć:

- mały, nieprzenikalny obszar fizyczny odpowiadający rzeczywistemu zajęciu miejsca przez rower i kolarza;
- większą miękką strefę bezpieczeństwa używaną do planowania manewrów.

Miękkie strefy mogą częściowo się nakładać w ciasnej grupie. Twarde obszary nie mogą się przenikać.

Jeżeli zawodnik ma większą docelową prędkość, ale z lewej i prawej strony nie istnieje bezpieczna luka, system nie może teleportować go, odpychać innych modeli ani przepuszczać przez zawodnika z przodu. Powinien chwilowo utrzymać pozycję na kole i ograniczyć rzeczywistą prędkość do dostępnej przestrzeni, aż pojawi się bezpieczna możliwość wyprzedzenia.

W sytuacji konfliktu zawodnik jadący z przodu domyślnie utrzymuje linię, a odpowiedzialność za znalezienie bezpiecznego toru spoczywa na zawodniku wyprzedzającym. Zapobiega to wzajemnemu „uciekaniu” obu modeli na tę samą stronę.


### No Static Wall, naturalne luki i brak „VIP lane”

Automatyczne pozycjonowanie nie może przypadkowo tworzyć trwałej „ściany” zawodników blokującej całą użyteczną szerokość drogi.

Jednocześnie system nie może sztucznie utrzymywać zawsze pustego pasa wyprzedzania ani rozsuwać peletonu tylko dlatego, że gracz chce jechać szybciej. Zwarta grupa, wachlarz przy bocznym wietrze, wąska droga albo realne zagęszczenie mogą czasowo zajmować praktycznie całą dostępną szerokość.

Solver nie powinien układać zawodników w idealne, statyczne rzędy poprzeczne, jeżeli nie wynika to z geometrii drogi, warunków jazdy albo jawnej przyszłej logiki taktycznej. Preferowane jest naturalne, lekko przesunięte ustawienie, ale nie wolno wymuszać sztucznej luki.

Obowiązują następujące invariants:

- `No Static Wall`: Pack Dynamics nie może utrzymywać pełnego blokowania drogi wyłącznie jako artefaktu automatycznego pozycjonowania;
- `No VIP Lane`: system nie może tworzyć gwarantowanego pustego korytarza tylko dla gracza ani zmuszać kilku zawodników do nienaturalnego ustępowania;
- istniejący lub przewidywany korytarz wyprzedzania może zostać wykorzystany i krótkotrwale zarezerwowany, jeżeli wynika z naturalnej dynamiki grupy;
- `BOXED_IN` jest poprawnym stanem wtedy, gdy geometria drogi i rzeczywista zajętość przestrzeni fizycznie uzasadniają brak przejazdu;
- chwilowe zajęcie całej szerokości drogi może być prawidłowe, jeżeli wynika z prawdziwej sytuacji, np. zwężenia, zakrętu albo ustawienia w crosswindzie;
- zwykły system avoidance nie może być używany do świadomego blokowania drogi ani do tworzenia uprzywilejowanej ścieżki dla jednego zawodnika.

Jeżeli zawodnik generuje wyraźnie większą docelową prędkość, system może użyć mechanizmu `Passing Opportunity Negotiation`.

Mechanizm powinien:

1. wykryć przyszły konflikt i brak bezpośredniej luki;
2. wyszukać istniejącą lub przewidywaną naturalną możliwość wyprzedzenia;
3. zarezerwować wykrytą lukę na krótki czas, aby kilku agentów nie próbowało wykorzystać jej jednocześnie;
4. dopuścić jedynie małe korekty innych zawodników, które same w sobie są uzasadnione collision avoidance, stabilnością linii albo naturalną dynamiką grupy;
5. nie tworzyć korytarza przez arbitralne rozpychanie kilku riderów;
6. utrzymać decyzję przez czas commitment/hysteresis;
7. zwolnić rezerwację po zakończeniu lub anulowaniu manewru.

System nie może gwarantować wyprzedzenia. Na wąskiej drodze, przy barierach, w zakręcie, w crosswindzie lub przy rzeczywistym zagęszczeniu grupy zawodnik może pozostać `BOXED_IN`.

Świadome taktyczne blokowanie drogi, jeżeli kiedykolwiek zostanie dodane, musi być osobną logiką AI/taktyki, a nie efektem ubocznym collision avoidance lub Pack Dynamics.

### Trajektoria i prezentacja manewru

Automatyczna korekta boczna musi być realizowana jako ciągła trajektoria jazdy, a nie translacja modelu w bok.

Trajektoria powinna mieć ograniczenia dotyczące co najmniej:

- prędkości bocznej;
- przyspieszenia bocznego;
- gwałtowności zmiany przyspieszenia;
- krzywizny toru lub efektywnego kąta skrętu.

Warstwa prezentacji musi pozostawać zgodna z wybraną trajektorią: zmiana toru powinna powodować odpowiedni yaw, wizualny skręt kierownicy i pochylenie roweru/kolarza. Gracz nie steruje tym bezpośrednio, ale manewr ma wyglądać jak rzeczywiste prowadzenie roweru.

### Drafting i zachowanie grupy

Docelowy Pack Dynamics powinien obejmować:

- drafting oparty na zmianie efektywnego oporu aerodynamicznego, a nie sztucznym bonusie do prędkości;
- automatyczne utrzymywanie koła;
- stabilizację pozycji i ograniczenie niepotrzebnego „churnu” w peletonie;
- automatyczne wyprzedzanie wynikające z różnicy docelowych prędkości;
- utratę koła, powrót do grupy i domykanie luki;
- zachowanie grupy w zakrętach;
- później także wpływ bocznego wiatru, wachlarze i zaawansowaną dynamikę ucieczek.

Logika fizyki podłużnej, interakcji grupy, planowania trajektorii bocznej oraz animacji/prezentacji powinna pozostać rozdzielona i testowalna.

### Sąsiedztwo zgodne z topologią trasy

Interakcje Pack Dynamics nie mogą być wyznaczane wyłącznie na podstawie odległości w światowym XYZ.

Na serpentynie, moście, w tunelu, na trasie wielopoziomowej albo na różnych okrążeniach dwóch riderów może znajdować się blisko geometrycznie, ale daleko wzdłuż faktycznej trasy.

Drafting, collision prediction, `BOXED_IN`, `GapReservation` i inne interakcje grupowe powinny wymagać zgodności topologicznej, np. zgodnego segmentu/korytarza trasy, sensownej różnicy `routeProgress` oraz — gdy będzie potrzebne — `lapIndex`.

Fałszywa bliskość przestrzenna nie może tworzyć draftu ani kolizji między zawodnikami jadącymi po innych fragmentach trasy.

### Hierarchia priorytetów planera

W sytuacji konfliktu pomiędzy poprawnymi lokalnie celami obowiązuje deterministyczna hierarchia priorytetów:

1. brak twardej kolizji;
2. pozostanie w dozwolonej geometrii drogi;
3. przyczepność i ograniczenia kinematyczne roweru;
4. bezpieczne dokończenie już committed manewru albo kontrolowany abort;
5. bezpieczeństwo i stabilność lokalnej grupy;
6. intencja podłużna wynikająca z realnej mocy użytkownika;
7. pozycja aerodynamiczna i drafting;
8. komfort, estetyka i preferowana linia.

Niższy priorytet nie może łamać wyższego. Korzystniejszy draft nie uzasadnia kolizji, a atrakcyjny passing corridor nie uzasadnia przekroczenia gripu na mokrym zakręcie.

### Brak magazynowania niewykorzystanej energii

Jeżeli automatyczne prowadzenie chwilowo ogranicza rzeczywistą prędkość, np. z powodu `BOXED_IN`, wygenerowana przez użytkownika moc nie może być magazynowana i później oddawana jako dodatkowy boost.

Energia, która z powodu automatycznego hamowania lub ograniczenia ruchu nie została zamieniona na wzrost energii kinetycznej/potencjalnej zgodnie z modelem, powinna zostać rozliczona jako strata, np. `WastedEnergy`.

Po otwarciu luki zawodnik przyspiesza wyłącznie na podstawie aktualnej realnej mocy i bieżącego stanu fizycznego.

### Pack Dynamics Torture Harness

Przed uznaniem Pack Dynamics za gotowy należy przygotować deterministyczny harness bez renderingu, który celowo próbuje złamać solver.

Minimalne klasy scenariuszy:

- dwóch riderów wybierających tę samą stronę uniku;
- dwóch riderów konkurujących o tę samą lukę;
- zamknięcie luki po rozpoczęciu manewru;
- sytuacja idealnie symetryczna wymagająca stabilnego tie-breakera;
- sztuczna pełna ściana na szerokiej drodze;
- realne zwężenie z prawidłowym `BOXED_IN`;
- crosswind/echelon zajmujący większość szerokości drogi;
- szybka i chwilowa zmiana wiatru;
- hairpin z próbą wyprzedzania;
- mokry zakręt z geometrycznie dostępną, ale kinematycznie niebezpieczną luką;
- szczyt podjazdu i nagłe rozciąganie grupy;
- szybki zjazd wymagający dłuższego prediction horizon;
- bardzo wolny podjazd;
- zatrzymany zawodnik;
- merge i split grup;
- serpentyny, mosty, tunele i różne poziomy trasy;
- różne `lapIndex`;
- finisz, przy którym niepotrzebny `RETURN_TO_LINE` nie może pogorszyć wyniku;
- chwilowy dropout mocy oraz nierealistyczny spike wejścia;
- zniknięcie/spawn ridera w przyszłym multiplayerze;
- recovery z już istniejącego overlapu bez „eksplozji” impulsowej.

Każdy test powinien sprawdzać co najmniej:

- `no hard overlap`;
- `no teleport`;
- `no road exit`;
- `no impossible lateral acceleration`;
- `no oscillation above threshold`;
- `no persistent artificial deadlock`;
- `no energy banking`;
- `no false cross-route interaction`;
- `no forced VIP lane`;
- `same inputs + same initial state -> same result`.

Prediction horizon i margines bezpieczeństwa powinny być zależne od prędkości i sytuacji. Rozwiązanie poprawne przy 8 km/h nie może być automatycznie uznane za poprawne przy 80 km/h.

Implementacja Pack Dynamics nie rozpoczyna się przed ukończeniem odpowiedniego etapu po MVP.

## 21. Road Guidance Overlay System

YetAnotherCyclingSim może wyświetlać kontekstowe oznaczenia rysowane bezpośrednio na drodze, aby wyjaśniać graczowi decyzje automatycznego prowadzenia i sytuację na trasie.

System nie powinien stale pokrywać drogi dużą liczbą znaczników. Oznaczenia mają pojawiać się tylko wtedy, gdy przekazują istotną informację potrzebną do podjęcia decyzji dotyczącej mocy lub zrozumienia zachowania automatycznego prowadzenia.

### Zasada projektowa

Road Guidance Overlay powinien przede wszystkim odpowiadać na pytanie:

**„Dlaczego system właśnie tak prowadzi rower lub dlaczego moja moc nie przekłada się teraz bezpośrednio na większą prędkość?”**

Oznaczenia nie służą do ręcznego sterowania lewo/prawo. Gracz nadal nie ma bezpośredniego wejścia kierunkowego.

### Corner Guidance — zakres MVP

Dla zakrętów system może wizualizować na drodze:

- zalecany tor przejazdu;
- strefę przygotowania i odpuszczenia mocy;
- obszar apeksu;
- strefę wyjścia i bezpiecznego powrotu do mocy;
- ostrzeżenie o pogorszonej przyczepności;
- ostrzeżenie o trudnym zakręcie po szybkim zjeździe;
- ostrzeżenie o szczycie podjazdu lub innym punkcie wymagającym wcześniejszej reakcji.

Oznaczenia powinny być zgodne z istniejącym systemem oceny techniki zakrętów i poziomem asysty.

### Pack Guidance — po MVP

Po wprowadzeniu Pack Dynamics system może dodatkowo wizualizować:

- `DRAFT_POCKET` — obszar korzystnego aerodynamicznie ustawienia;
- `HOLD_WHEEL` — sytuację, w której najlepszym zachowaniem jest utrzymanie koła;
- `BOXED_IN` — brak bezpiecznej przestrzeni do wyprzedzania;
- `PASS_CORRIDOR_LEFT` i `PASS_CORRIDOR_RIGHT` — wykryty i zarezerwowany bezpieczny korytarz wyprzedzania;
- ostrzeżenie o przewidywanym konflikcie lub zamykającej się luce;
- strefę kompresji grupy;
- zwężenie drogi wymagające wcześniejszego ustawienia;
- strefę silnego bocznego wiatru lub późniejszy korytarz ustawienia w wachlarzu.

Korytarz wyprzedzania jest informacją o planie automatycznego prowadzenia, a nie poleceniem skrętu dla użytkownika.

### Warstwa Hazard Guidance

System może pokazywać na drodze krótkotrwałe ostrzeżenia dotyczące:

- mokrej lub śliskiej nawierzchni;
- lokalnego spadku przyczepności;
- zwężenia;
- ostrego zakrętu;
- kompresji peletonu;
- bocznego wiatru;
- miejsca, w którym aktualna sytuacja może doprowadzić do utraty koła.

### Spójność wizualna

Oznaczenia powinny być subtelne i czytelne. Preferowane są:

- spline-based overlays;
- projected decals;
- półprzezroczyste pasy;
- lekkie strzałki;
- delikatne pulsowanie;
- krótkie animacje wejścia i zaniku.

System nie powinien wyglądać jak neonowy tor wyścigowy ani zasłaniać świata 3D.

Semantyka koloru powinna pozostać spójna w całej grze. Przykładowo:

- neutralny jasny kolor — tor prowadzący;
- żółty — przygotowanie lub uwaga;
- pomarańczowy — istotne ostrzeżenie;
- czerwony — brak miejsca lub wysokie ryzyko;
- zielony — bezpieczny moment przyspieszenia;
- niebieski — korzyść aerodynamiczna.

Dokładne kolory wymagają późniejszej walidacji dostępności i czytelności.

Kolor nie może być jedynym nośnikiem znaczenia. Ważne stany powinny różnić się także kształtem, wzorem, animacją lub ikonografią.

Jeżeli jednocześnie aktywnych jest kilka typów guidance, np. zakręt, `BOXED_IN`, crosswind i niski grip, `GuidanceComposer` powinien ustalić priorytet i ograniczyć liczbę równocześnie widocznych sygnałów. Droga nie może zamieniać się w nakładającą się „choinkę” oznaczeń.

Czytelność należy walidować co najmniej dla różnych kamer, deszczu, jasnej i ciemnej nawierzchni oraz warunków ograniczonej widoczności.

### Poziomy asysty

Zakres Road Guidance powinien zależeć od poziomu asysty.

Niski poziom:
- minimalne oznaczenia;
- podstawowe ostrzeżenia;
- linia zakrętu tylko wtedy, gdy jest potrzebna.

Średni poziom:
- pełniejsze Corner Guidance;
- podstawowe ostrzeżenia sytuacyjne.

Wysoki poziom:
- rozbudowane wskazówki zakrętowe;
- po MVP również Pack Guidance i korytarze sytuacyjne.

Tryb ekspercki lub immersyjny:
- możliwość ograniczenia lub wyłączenia większości oznaczeń.

### Pewność wskazania

System może wizualnie odróżniać wskazania o wysokiej i niskiej pewności.

Przykład:
- ciągłe i wyraźne oznaczenie — stabilna rekomendacja;
- krótkie, słabsze lub przerywane oznaczenie — sytuacja dynamiczna albo przewidywanie o niższej pewności.

Nie wolno jednak generować pozornie precyzyjnego guidance, jeżeli system nie posiada wystarczających danych do wiarygodnej rekomendacji.

### Rozdzielenie logiki i prezentacji

Road Guidance Overlay jest warstwą prezentacji. Nie może być źródłem prawdy dla fizyki ani Pack Dynamics.

Kolejność zależności powinna pozostać jednokierunkowa:

`Physics / Route / Pack Dynamics → Guidance State → Road Overlay`

Wyłączenie overlayu nie może zmieniać fizyki, toru jazdy ani zachowania automatycznego prowadzenia.

## 22. Rider Technical Profile (po MVP)

Po MVP profil zawodnika może zostać rozszerzony o cechy techniczne wpływające na jakość automatycznego prowadzenia, szczególnie w trudnych i granicznych sytuacjach.

### Zasada projektowa

Parametry fizyczne określają fizyczne możliwości zawodnika i roweru. Umiejętności techniczne nie mogą tworzyć sztucznych bonusów do prędkości, mocy ani przyczepności.

Należy rozdzielić trzy różne pojęcia:

- `PhysicalCapability` — realna moc, masa, `CdA`, `Crr` i inne fizyczne możliwości;
- `PlayerTechnique` — umiejętności zależne od decyzji, które użytkownik rzeczywiście podejmuje, np. timing mocy/kadencji, reakcja na guidance i technika zakrętów;
- `AutopilotProficiency` — parametry automatycznego prowadzenia, np. ostrożność planera, marginesy bezpieczeństwa i sposób wykorzystania luki.

`PlayerTechnique` może podlegać progresji tylko wtedy, gdy wynik jest rzeczywiście związany z zachowaniem użytkownika.

`AutopilotProficiency` nie może rozwijać się automatycznie tylko dlatego, że autopilot sam wykonał udany manewr. W przeciwnym razie powstałaby pętla: lepszy autopilot → więcej sukcesów → jeszcze lepszy autopilot bez realnej nauki użytkownika.

Przykładowe przyszłe cechy wymagające dalszego projektu:

- `CorneringTechnique` — kandydat na `PlayerTechnique`;
- `PackTiming` lub podobna cecha związana z realnym timingiem mocy użytkownika — kandydat na `PlayerTechnique`;
- `PackHandling` i `BikeHandling` muszą zostać przed implementacją sklasyfikowane jako faktyczna technika użytkownika albo parametr `AutopilotProficiency`; nie wolno mieszać tych kategorii.

W przyszłym trybie competitive multiplayer parametry `AutopilotProficiency` powinny być co najmniej rozważone do normalizacji, aby przewaga nie wynikała z tego, że system prowadzi rower lepiej za jednego gracza niż za drugiego.

Dokładny zestaw cech i ich sposób prezentacji wymagają osobnego projektu po MVP.

### Pack Handling

`PackHandling` może wpływać między innymi na:

- minimalny komfortowy odstęp od innych zawodników;
- jakość utrzymywania koła;
- szybkość i stabilność reakcji na otwierającą się lub zamykającą lukę;
- skuteczność `Passing Opportunity Negotiation`;
- zdolność do wykorzystania krótkotrwałego korytarza wyprzedzania;
- wielkość marginesu bezpieczeństwa używanego przez planner;
- płynność reakcji na kompresję i rozciąganie grupy;
- skuteczność domykania małych luk;
- stabilność pozycji przy bocznym wietrze;
- ilość energii traconej przez niepotrzebne hamowanie i ponowne rozpędzanie.

Wyższa wartość cechy nie może:

- umożliwiać przenikania modeli;
- zmniejszać twardego obszaru kolizji poniżej bezpiecznego minimum;
- pozwalać na przejazd przez fizycznie niemożliwą lukę;
- omijać ograniczeń geometrii drogi;
- gwarantować powodzenia manewru;
- łamać zasad `No Static Wall` ani innych invariants Pack Dynamics.

### Technical Demand i Technical Capacity

Trudne sytuacje mogą być opisywane przez poziom `TechnicalDemand`, zależny przykładowo od:

- względnej prędkości zawodników;
- gęstości grupy;
- dostępnego prześwitu;
- szerokości drogi;
- krzywizny zakrętu;
- bocznego wiatru;
- tempa zmian lokalnej sytuacji.

Profil zawodnika dostarcza odpowiadający poziom `TechnicalCapacity`.

System powinien pozostawać deterministyczny dla tych samych wejść i nie opierać wyniku podstawowych manewrów na losowym rzucie procentowym.

Przykładowa interpretacja:

- `TechnicalDemand < TechnicalCapacity` — możliwy jest płynny i efektywny manewr;
- `TechnicalDemand ≈ TechnicalCapacity` — system wybiera bardziej zachowawczy manewr z większym marginesem;
- `TechnicalDemand > TechnicalCapacity` — możliwe jest przegapienie krótkiej luki, większe hamowanie, późniejsze domknięcie luki albo utrata koła.

### Parametry fizyczne postaci

Wzrost i masa mogą zostać użyte do określenia rzeczywistych parametrów fizycznych lub geometrii zawodnika.

Masa wpływa poprzez model fizyczny.

Wzrost może wpływać między innymi na:

- geometryczny footprint zawodnika;
- wysokość i proporcje modelu;
- wymagany prześwit podczas wyprzedzania;
- wielkość obszaru zajmowanego przez zawodnika;
- parametry aerodynamiczne tylko wtedy, gdy zostanie zdefiniowany wiarygodny model zależności.

Nie należy stosować prostych reguł typu „większy wzrost = gorsze aero”. `CdA` pozostaje osobnym parametrem fizycznym, który może być wyliczany lub proponowany przez preset, ale nie powinien wynikać z arbitralnego mnożnika RPG.

### Edge cases

Umiejętności techniczne mają największe znaczenie w sytuacjach granicznych, np.:

- nagła kompresja grupy przed zakrętem;
- krótko dostępna luka do wyprzedzania;
- mała luka powstała po zakręcie;
- gwałtowna zmiana ustawienia ridera przed użytkownikiem;
- crosswind i walka o korzystniejszą pozycję;
- ciasne, ale nadal fizycznie możliwe wyprzedzanie.

W każdej z tych sytuacji wyższa technika powinna poprawiać jakość decyzji automatycznego prowadzenia, ale nie zmieniać twardych ograniczeń fizycznych.

### Pack Technique Score

Po MVP system może raportować jakość jazdy w grupie za pomocą `PackTechniqueScore`.

Przykładowe metryki:

- `DraftEfficiency`;
- `WheelHolding`;
- `GapClosureSuccess`;
- `WastedEnergy`;
- `MissedPassingOpportunities`;
- czas spędzony poza korzystnym draftem;
- liczba zbędnych mikrohamowań.

Ocena ma pomagać użytkownikowi zrozumieć skuteczność jazdy w grupie i rozwijać technikę, a nie ukrywać wynik za jednym losowym numerem.


### Power Integrity — realna moc jest nadrzędna

Moc dostarczana przez trenażer lub inne rzeczywiste źródło wejścia jest nadrzędnym źródłem osiągów zawodnika.

Obowiązuje twarda zasada:

**Real trainer power determines what the rider can physically do. Technical skill determines how efficiently the automatic riding system uses those watts in difficult situations.**

Umiejętności techniczne nie mogą bezpośrednio modyfikować:

- `PowerWatts`;
- FTP;
- masy zawodnika;
- masy roweru;
- grawitacji;
- `Crr`;
- bazowego `CdA`;
- mocy dostarczanej przez trenażer;
- innych podstawowych parametrów fizycznych w celu sztucznego zwiększenia osiągów.

Niedopuszczalne są rozwiązania typu:

`EffectivePower = TrainerPower * SkillBonus`

albo inne ukryte mnożniki tworzące „wirtualne waty”.

Dla identycznych parametrów fizycznych dwóch zawodników generujących tę samą moc na pustej, prostej drodze powinno uzyskać ten sam wynik niezależnie od `PackHandling`, `CorneringTechnique` lub innych cech technicznych.

Skill może wpływać dopiero wtedy, gdy sytuacja wymaga decyzji lub wykonania technicznego.

### Skill wpływa na straty, a nie tworzy energii

Podstawową interpretacją cech technicznych jest ograniczanie niepotrzebnych strat, a nie zwiększanie dostępnej energii.

Lepsza technika może zmniejszać między innymi:

- energię utraconą przez niepotrzebne hamowanie;
- liczbę mikroprzyspieszeń po źle zamkniętej luce;
- czas spędzony poza optymalnym draftem;
- liczbę przegapionych bezpiecznych okazji do wyprzedzania;
- koszt energetyczny niestabilnego utrzymywania koła;
- straty wynikające z zachowawczych reakcji w edge case'ach.

Całkowita energia wynikająca z wejścia użytkownika pozostaje niezmieniona.

System może raportować rozdzielenie energii na użyteczny napęd i straty sytuacyjne, ale nie może przypisywać skillom dodatkowej energii, której użytkownik faktycznie nie wygenerował.

### Priorytet wysiłku użytkownika nad progresją

Progres postaci jest zawsze drugorzędny wobec rzeczywistego wysiłku użytkownika.

Zawodnik o wysokim skillu i niższej mocy może efektywniej korzystać z draftu, lepiej utrzymywać pozycję i tracić mniej energii, ale nie może automatycznie pokonać zawodnika generującego istotnie większą rzeczywistą moc, jeżeli sytuacja wymaga tej mocy.

Jeżeli utrzymanie grupy lub wykonanie manewru fizycznie wymaga większej mocy niż użytkownik dostarcza, zawodnik powinien stracić koło, zwolnić lub nie ukończyć manewru niezależnie od poziomu skilla.

### Skill Progression

Rozwój umiejętności technicznych nie powinien opierać się na prostym grindzie kilometrów, czasu gry ani liczby przejazdów.

Progres nie może być przyznawany za zdarzenie, którego wynik został w całości wygenerowany przez automatyczne prowadzenie. System progresji musi potrafić wskazać, jaki kontrolowany przez użytkownika sygnał lub decyzja miały wpływ na oceniane zachowanie.

Preferowany model progresji:

- łatwe sytuacje znacznie poniżej aktualnego poziomu zawodnika dają minimalny lub zerowy progres;
- największy progres pojawia się przy poprawnym wykonaniu sytuacji, w których `TechnicalDemand` jest blisko aktualnego `TechnicalCapacity`;
- sytuacje znacznie przekraczające aktualne możliwości nie powinny przyznawać dużej nagrody tylko za samo ich wystąpienie;
- powtarzanie jednego banalnego scenariusza nie może być efektywną metodą farmienia skilla;
- progres powinien odzwierciedlać skuteczne zachowanie w realnych, zróżnicowanych sytuacjach.

Przykładowo `PackHandling` może rozwijać się za:

- stabilne utrzymywanie koła w trudnych warunkach;
- skuteczne domykanie luk;
- poprawne wykorzystanie krótkiego korytarza wyprzedzania;
- płynne przejście przez kompresję grupy;
- ograniczenie `WastedEnergy`;
- stabilne zachowanie przy bocznym wietrze;
- poprawne decyzje w edge case'ach.

Dokładny model progresji wymaga osobnego balansu i walidacji telemetrycznej.

### Balancing Requirements

System skillów musi być projektowany jako mechanika łatwa do strojenia bez zmiany podstawowego kodu fizyki.

Parametry wpływu skilla powinny być konfigurowalne i obejmować co najmniej:

- ograniczony minimalny i maksymalny wpływ;
- krzywe efektu;
- diminishing returns;
- progi `TechnicalDemand`;
- progi `TechnicalCapacity`;
- limity marginesów bezpieczeństwa;
- limity wpływu na reakcję planera.

Przejście z niskiego do średniego poziomu może być zauważalne, ale bardzo wysoki skill nie może tworzyć nieproporcjonalnej przewagi.

Przykładowo progres z poziomu średniego do dobrego może następować relatywnie szybko, natomiast bardzo wysokie poziomy powinny wymagać wielu poprawnie wykonanych trudnych sytuacji.

Przed wdrożeniem progresji należy przygotować deterministyczny balancing harness obejmujący dużą liczbę scenariuszy `TechnicalDemand × TechnicalCapacity`.

Harness powinien sprawdzać między innymi:

- wpływ skilla na `WastedEnergy`;
- częstość utraty koła;
- skuteczność domykania luk;
- wykorzystanie krótkich passing corridors;
- reakcję na kompresję grupy;
- zachowanie przy różnej szerokości drogi;
- zachowanie przy różnym crosswindzie;
- brak naruszeń hard collision i innych invariants.

Balans powinien być później korygowany na podstawie rzeczywistej telemetrii z jazd, a nie wyłącznie na podstawie intuicji projektowej.

### Zasada końcowa

**Hardware / real effort first, character progression second.**

Wat z trenażera jest źródłem energii. Skill może poprawiać jakość wykorzystania tej energii, ale nigdy nie może jej tworzyć.

## 23. Feedback zastępczy dla brakujących bodźców fizycznych

YetAnotherCyclingSim jest symulatorem jazdy na trenażerze, dlatego część bodźców dostępnych podczas prawdziwej jazdy nie jest fizycznie odczuwalna przez użytkownika.

Gra musi świadomie kompensować ten brak przez dobrze przemyślany feedback wizualny i, tam gdzie ma to sens, dźwiękowy.

### Zasada projektowa

Jeżeli podczas prawdziwej jazdy kolarz otrzymałby ważną informację przez:

- balans ciała i roweru;
- nacisk na kierownicę;
- zmianę siły bocznej;
- kontakt i bliskość innych zawodników;
- opór wynikający z ciasnej pozycji w grupie;
- poczucie zamknięcia lub braku miejsca;
- poślizg lub spadek przyczepności;
- podmuch bocznego wiatru;
- turbulencję;
- zmianę wymaganej linii jazdy;
- ryzyko utraty koła;

a użytkownik na trenażerze nie może wiarygodnie otrzymać tego bodźca fizycznie, system powinien przekazać równoważną informację przez czytelny feedback prezentacyjny.

### Wymagania

Feedback zastępczy powinien:

- pojawiać się tylko wtedy, gdy przekazuje istotną informację;
- być jednoznaczny co do przyczyny;
- pojawiać się wystarczająco wcześnie, aby użytkownik mógł zareagować mocą lub kadencją;
- odróżniać ostrzeżenie od stabilnej rekomendacji;
- być spójny między zakrętami, Pack Dynamics, pogodą i innymi systemami;
- nie zasłaniać świata ani nie przeciążać ekranu;
- unikać arcade'owego charakteru, jeżeli prostszy i bardziej naturalny sygnał wystarcza;
- respektować poziom asysty i możliwość ograniczenia lub wyłączenia części wskazówek.

### Przykłady zastosowania

Przykładowe sytuacje wymagające wyraźnego feedbacku:

- `BOXED_IN` — gracz widzi, że większa moc nie przekłada się chwilowo na wyprzedzanie z powodu braku miejsca;
- `SEARCHING_FOR_GAP` — system informuje, że szuka bezpiecznego korytarza;
- `PASS_CORRIDOR_LEFT` / `PASS_CORRIDOR_RIGHT` — wizualizacja planowanego automatycznego manewru;
- `DRAFT_POCKET` i `HOLD_WHEEL` — informacja o korzystnym ustawieniu aerodynamicznym;
- utrata korzystnego draftu — czytelne pokazanie, że zawodnik zaczyna tracić koło;
- kompresja grupy — sygnał, że sytuacja wymaga ograniczenia mocy lub przygotowania na zmianę tempa;
- crosswind — informacja o częściowej ekspozycji na wiatr i zmianie korzystnego ustawienia;
- niski grip — ostrzeżenie o mniejszym marginesie przyczepności;
- zakręt — linia, entry/apex/exit i moment bezpiecznego powrotu do mocy;
- wysoki `TechnicalDemand` — subtelne wskazanie, że aktualna sytuacja jest technicznie wymagająca.

### Feedback musi wyjaśniać zachowanie automatyki

Jeżeli automatyczne prowadzenie:

- ogranicza prędkość;
- nie rozpoczyna wyprzedzania;
- rezygnuje z luki;
- zmienia planowany korytarz;
- zwiększa margines bezpieczeństwa;
- pozwala utracić koło;
- wybiera zachowawczy tor;

gracz powinien móc zrozumieć przyczynę bez zgadywania, że system działa losowo lub jest zepsuty.

### Hierarchia feedbacku

Preferowana kolejność przekazywania informacji:

1. świat i animacja — zachowanie roweru, pochylenie, tor, ruch grupy;
2. oznaczenie bezpośrednio na drodze lub w przestrzeni świata;
3. dyskretny element HUD;
4. krótki komunikat tekstowy tylko wtedy, gdy wcześniejsze warstwy nie są wystarczające.

Celem jest maksymalne wykorzystanie naturalnej prezentacji świata, a nie zastępowanie wszystkiego komunikatami HUD.

### Rozdzielenie odpowiedzialności

Feedback jest prezentacją już istniejącego stanu symulacji.

Zależność pozostaje jednokierunkowa:

`Physics / Route / Pack Dynamics / Technical State → Feedback State → Visual / Audio Presentation`

Warstwa feedbacku nie może zmieniać wyniku fizyki, decyzji Pack Dynamics ani wartości skilla.

### Walidacja czytelności

Każda ważna mechanika bez naturalnego fizycznego feedbacku powinna podczas implementacji otrzymać test UX odpowiadający na pytania:

- czy gracz rozumie, co się właśnie wydarzyło;
- czy rozumie, dlaczego system zachował się w ten sposób;
- czy wie, czy powinien zmienić moc lub kadencję;
- czy potrafi rozróżnić ograniczenie fizyczne od decyzji automatycznego prowadzenia;
- czy feedback jest wystarczająco widoczny, ale nie przeszkadza w obserwowaniu świata.

Mechanika nie powinna być uznana za ukończoną, jeżeli jej kluczowy stan jest niewidoczny dla gracza i nie ma realnego odpowiednika haptycznego lub kinestetycznego.

