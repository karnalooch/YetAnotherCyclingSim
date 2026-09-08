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