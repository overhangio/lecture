import io
import re
import typing as t

from bs4 import BeautifulSoup

from lecture import units
from lecture.exceptions import LectureError
from lecture.formats.base.reader import Reader as BaseReader
from lecture.utils import youtube


def load(path: str) -> units.Course:
    reader = FilesystemReader(path)
    return reader.read()


def get_header_level(h: str) -> t.Optional[int]:
    match = re.match(r"h([1-9])", h)
    if not match:
        return None
    return int(match.group(1))


class Reader(BaseReader):
    def __init__(self, unit_html: BeautifulSoup) -> None:
        self.unit_html = unit_html

    def parse(self) -> t.Iterable[units.Unit]:
        """
        In this method we only detect the headers. Parsing the actual content of each
        unit is done in the `on_header` method.
        """
        header_level = get_header_level(self.unit_html.name)
        if not header_level:
            # TODO how to we make all of this also work for non-header units?
            return

        for unit in self.dispatch(self.unit_html.name, self.unit_html):
            for next_html in self.unit_html.find_next_siblings():
                next_header_level = get_header_level(next_html.name)
                if not next_header_level:
                    continue
                if next_header_level == header_level + 1:
                    # Next level, create a child unit
                    for child in Reader(next_html).parse():
                        unit.add_child(child)
                elif next_header_level <= header_level:
                    # We found a header with the same level or a parent unit. All
                    # subsequent items belong to it.
                    break
            yield unit

    def on_header(self, unit_html: BeautifulSoup) -> t.Iterable[units.Unit]:
        # Create unit
        UnitClass = units.Course if unit_html.name == "h1" else units.Unit
        attributes = {
            k[5:]: v for k, v in unit_html.attrs.items() if k.startswith("data-")
        }
        unit: units.Unit = UnitClass(attributes, title=self.unit_html.string.strip())

        # Find children
        children = []
        for child_html in unit_html.find_next_siblings():
            if not getattr(child_html, "name"):
                # Skip raw strings
                # TODO wait do we really want to do that?
                continue
            if get_header_level(child_html.name) is not None:
                # Child is a header: stop processing
                break
            for child in self.dispatch(child_html.name, child_html):
                children.append(child)

        for child in children:
            if (
                isinstance(child, units.RawHtml)
                and unit.children
                and isinstance(unit.children[-1], units.RawHtml)
            ):
                # Concatenate all RawHtml children
                unit.children[-1].concatenate(child)
            else:
                # Append child
                unit.add_child(child)

        yield unit

    def _on_html(self, unit_html: BeautifulSoup) -> t.Iterable[units.Unit]:
        # TODO copy data-* attributes?
        yield units.RawHtml(contents=str(unit_html))

    # Add here all html elements that should be converted to RawHtml
    on_div = _on_html
    on_p = _on_html
    on_pre = _on_html

    def on_ul(self, unit_html: BeautifulSoup) -> t.Iterable[units.Unit]:
        """
        <ul> tags may contain multiple choice questions. In such cases, the first <li>
        is the question and each subsequent <li> element starts with either ✅ or ❌.
        """
        question: t.Optional[str] = None
        answers_are_valid = True
        right = "✅"
        wrong = "❌"
        answers = []
        for li_html in unit_html.find_all("li"):
            answer = li_html.string.strip()
            if question is None:
                question = answer
            elif answer.startswith(right):
                answers.append((answer[1:].strip(), True))
            elif answer.startswith(wrong):
                answers.append((answer[1:].strip(), False))
            else:
                # Not a multiple choice question
                answers_are_valid = False
                break
        if question is not None and answers_are_valid:
            # Generate MCQ
            # Note that the question is parsed from the previous <p>
            yield units.MultipleChoiceQuestion(
                question=question,
                answers=answers,
            )
            return

        # Process as a normal html element
        yield from self._on_html(unit_html)

    def on_iframe(self, unit_html: BeautifulSoup) -> t.Iterable[units.Unit]:
        """
        We only parse video units.
        TODO parse arbitrary html/iframe content?
        """
        src = unit_html.attrs.get("src")
        if youtube_video_id := youtube.get_embed_video_id(src):
            yield units.Video(sources=[youtube.get_watch_url(youtube_video_id)])

    on_h1 = on_header
    on_h2 = on_header
    on_h3 = on_header
    on_h4 = on_header
    on_h5 = on_header
    on_h6 = on_header

    def on_video(self, video_html: BeautifulSoup) -> t.Iterable[units.Unit]:
        """
        https://developer.mozilla.org/en-US/docs/Web/HTML/Element/video
        """
        sources: t.List[str] = []
        if src := video_html.attrs.get("src"):
            sources.append(src)
        for source_html in video_html.find_all("source"):
            if source := source_html.attrs.get("src"):
                if source not in sources:
                    sources.append(source)
        yield units.Video(sources=sources)


class DocumentReader(Reader):
    def __init__(self, document: BeautifulSoup) -> None:
        if h1 := document.find(name="h1"):
            super().__init__(h1)
        else:
            raise LectureError("Could not find any h1 element in the HTML document")


class FilesystemReader(DocumentReader):
    def __init__(self, path: str) -> None:
        with open(path, encoding="utf-8") as f:
            super().__init__(beautiful_soup(f))


def beautiful_soup(src: t.Union[str, io.TextIOBase]) -> BeautifulSoup:
    return BeautifulSoup(src, "html5lib")
