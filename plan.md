Ziel der Anwendung: ein auf der DIP-API aufbauendes "Parla für den Bund".

Wir entwickeln eine KI-Anwendung, die ähnlich funktioniert wie Parla 
https://www.parla.berlin
https://github.com/technologiestiftung/parla-frontend
https://github.com/technologiestiftung/parla-api
https://github.com/technologiestiftung/parla-document-processor

Wir wollen Usern ermöglichen, Fragen an den Dokumentenkorpus des Bundestages zu stellen. Die dafür notwendige API stellt der Bund hier bereit:
https://dip.bundestag.de/%C3%BCber-dip/hilfe/api

Bekomme ein umfassendes Verständnis für das Projekt. Verstehe Parla, untersuche die DIP API, dann entwickle einen Umsetzungsplan für das Vorhaben. Bedenke vor allem die Herausforderungen, etwa den deutlich größeren Umfang der Dokumentenbasis. 

Dann entwickle einen Umsetzungplan, wie Parla-Bund technisch umgesetzt werden kann. Wir besprechen dann den Plan und treffen gemeinsam eine Entscheidung.

Im nächsten Schritt baust Du einen Prototypen, der das Prinzip verdeutlicht.

Als KI-Modell kannst Du auf Googles LLMs zugreifen, der API-Key liegt in der .env Datei.


Hintergrund-Infos:

# Product Requirement Document - Parla Bund

Version: 0.95
Letzte Änderung: 28.09.26

*Hinweis: Dieses Dokument ist eine Arbeitsgrundlage, kein Beschluss. Mit der fortlaufenden Entwicklung des Vorhabens, wächst auch dieses Dokument weiter.*

## 1. Zusammenfassung (Executive Summary)

Parla Bund ist ein KI-Fragetool, das aktuelle Fragen zur Arbeit des Deutschen Bundestages in Alltagssprache beantwortet und zu jeder Antwort die Drucksachen und Plenarprotokolle nachweist, auf denen sie beruht. Die Anwendung ist für Bürger:innen ohne spezielles Vorkenntnisse bestimmt.

Mit Parla Bund dauern Recherchen, die vorher Stunden gedauert haben, nur noch Minuten. Eine Suche, die nur mit Expertenwissen durchführbar war, kann jetzt ohne die diese Zugangshürde durchgeführt werden. Nutzer:innen stellen ihre Frage in einem Suchfeld in normaler Sprache. Parla Bund durchsucht daraufhin die öffentlich verfügbaren Parlamentsdokumente, fasst die relevanten Stellen zusammen und verlinkt jedes Dokument, aus dem die Antwort stammt. Wer tiefer einsteigen will, kommt mit einem Klick zum Originaltext. Wer nur schnell einen Überblick braucht, hat ihn in wenigen Sekunden.

Der Mehrwert für die Zielgruppe wird darin gemessen, in welcher **Geschwindigkeit** nutzbare Ergebnisse vorliegen und wie hoch die **Qualität** der Ergebnisse eingeschätzt wird. Baseline ist die bestehende Suchfunktion des Dokumenten-Informationsportal des Bundestages. Benchmark ist eine professionell durchgeführte Suche durch den Auskunftsdienst des Deutschen Bundestages.

Parla Bund verbessert die Transparenz über die Arbeit des Deutschen Bundestages und stärkt so das Vertrauen der Bürger:innen in das Parlament und die Demokratie insgesamt.

**Elevator Pitch: Parla Bund stärkt die Demokratie, indem es Bürger:innen ermöglicht, sich selbstständig und einfach aus erster Hand darüber zu informieren, was im Deutschen Bundestag diskutiert und beschlossen wird und wie ihn:sie das betrifft.**

---

## 2. Ausgangslage und Problem

### 2.1 Problembeschreibung

Der Deutsche Bundestag veröffentlicht eine große Menge parlamentarischer Dokumente, über die sich die Öffentlichkeit darüber informieren kann, was im Parlament diskutiert und beschlossen wird. Der Zugang zu diesen Dokument erfordert ein hohes Maß an Spezialwissen über die Arbeitsweise des Bundestages, die Dokumententypen und deren Aufbau, sowie über die speziellen Einstellmöglichkeiten der Suchfunktion.

Insbesondere Suchen, bei denen nicht von vornherein klar ist, in welchem Dokument die bzw. an welcher Stelle die Antwort zu finden ist, erfordern einen hohen zeitlichen Aufwand und stellen Nicht-Expert:innen vor hohe Hürden. Zudem können Antworten sich über mehrere Stellen, in mehreren Dokumenten verteilen, deren Zusammenhang sich nur durch Spezialwissen erschließen lässt.

Hinzu kommt, dass in den offiziellen Dokumenten in hohem Maße formalisierte Sprache und Fachbegriffe verwendet werden, die oftmals einer separaten Erklärung bedürfen. Auch der Kontext einer Information ist nicht immer durch Alltagswissen einordnenbar.

Im Ergebnis sind die Zugangshürden zu relevanten Informationen für Bürger:innen je nach Frage vielfach zu hoch und der zeitliche und kognitive Aufwand einer Recherche selbst für Expert:innen sehr hoch.

### 2.2 Warum jetzt?

Parla Berlin hat die technische Machbarkeit und Umsetzbarkeit durch das CityLAB Berlin unter Beweis gestellt und zudem die Entscheider:innen in der Bundestagsverwaltung vom Mehrwert dieser Lösung überzeugt. Die technologische Innovation (KI) ist ausgereift und es entspricht einem sich wandelnden Nutzer:innenverhalten, bei Recherchen auf KI zurückzugreifen. Das BMDS fördert die Initiative im Rahmen eines Hackathons.

### 2.3 Verhältnis zu Parla (Berlin)

| Aspekt | Parla Berlin (Ist) | Parla Bund v1 (Soll) |
| --- | --- | --- |
| Datenquelle | `PARDOK` | `DIP / DIP-API` |
| Dokumenttypen | `Schriftliche Anfragen, Rote Nummern` | `Anfragen, Plenumgsprotokolle, Gesetzesentwürfe, Anträge, Sitzungsvorlagen` |
| Betrieb / Hosting | CityLAB Berlin | `[…]` |
| Betreiberorganisation | CityLAB Berlin | `[…]` |
| Sprachmodell | Open AI GPT 40 mini | `[…]` |

---

## 3. Ziele

### 3.1 Produktziele

1. Politische Debatten und parlamentarische Initiativen in Alltagssprache darstellen
2. Fragen der Bürger:innen so beantworten, dass sie einen Bezug zum eigenen Lebenskontext herstellen können
3. Parlamentarische Prozesse nachvollziehbar machen