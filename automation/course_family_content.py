from __future__ import annotations

from dataclasses import replace
import re

from automation.models import Course


GENERALIZED_COURSE_CONTENT: dict[str, dict[str, object]] = {
    "data-vis": {
        "subtitle": "Course home across academic iterations",
        "summary": (
            "I teach Data Visualization at Tel Aviv University, covering visual encoding, dashboard design, "
            "storytelling, and the practical craft of turning complex data into clear visual arguments."
        ),
        "hero_note": (
            "This page collects shared materials from multiple iterations of the course together with links to "
            "individual semester pages."
        ),
        "manual_overrides": {
            "hide_empty_materials": True,
            "opening_paragraph": (
                "Across recent semesters, the course has combined conceptual foundations with hands-on visual "
                "analysis work. It starts from visual perception, task abstraction, and the grammar of charts, "
                "then moves through chart families, dashboard composition, critique, and data-driven storytelling, "
                "with Tableau used as a practical environment for implementing and evaluating visual ideas."
            ),
            "syllabus_markdown": "\n".join(
                [
                    "* Recent iterations begin with intro to data visualization, Tableau, and task/data abstraction.",
                    "* The middle of the course focuses on marks and channels, chart families, arrangement, and dashboard design.",
                    "* Later sessions cover data preparation, critique, and storytelling with visual analytics.",
                    "* Coursework typically combines in-class exercises, homework, and a final dashboard-based analysis project.",
                ]
            ),
        },
    },
    "deep-learning": {
        "subtitle": "Course home across academic iterations",
        "summary": (
            "I teach Deep Learning at Tel Aviv University as a hands-on course on modern neural networks, "
            "spanning optimization, CNNs, sequence models, transformers, and generative modeling in PyTorch."
        ),
        "hero_note": (
            "This page collects shared materials from multiple iterations of the course together with links to "
            "the concrete semester pages."
        ),
        "manual_overrides": {
            "hide_empty_materials": True,
            "opening_paragraph": (
                "Recent iterations have treated deep learning as both a conceptual and engineering subject. "
                "Students build models in PyTorch, reason about optimization and regularization, and work through "
                "image, text, and sequence problems before reaching transformer-based and generative methods."
            ),
            "syllabus_markdown": "\n".join(
                [
                    "* The course starts with neural networks, backpropagation, optimization, and practical training workflows.",
                    "* It continues through deep feedforward models, convolutional networks, and sequence models such as RNNs, LSTMs, and GRUs.",
                    "* Later sessions cover attention, transformers, transfer learning, and large-scale model training.",
                    "* Recent iterations also introduce generative modeling, including autoencoders, VAEs, GANs, and diffusion-style ideas.",
                    "* Assessment typically mixes class assignments, home assignments, and a final pair project.",
                ]
            ),
        },
    },
    "text-mining": {
        "subtitle": "Course home across academic iterations",
        "summary": (
            "I teach Text Mining at Tel Aviv University, covering classical NLP, representation learning, "
            "transformers, and modern LLM-based workflows for working with text as data."
        ),
        "hero_note": (
            "This page collects shared materials from multiple iterations of the course together with links to "
            "the relevant semester pages."
        ),
        "manual_overrides": {
            "hide_empty_materials": True,
            "opening_paragraph": (
                "The course starts from practical text preprocessing and classical bag-of-words baselines, then "
                "moves through embedding methods, sequence models, transformers, and contemporary LLM systems "
                "used for retrieval, summarization, extraction, and classification."
            ),
            "syllabus_markdown": "\n".join(
                [
                    "* It begins with text preprocessing, tokenization, normalization, bag-of-words, TF-IDF, and practical pipelines in Python.",
                    "* The next part covers classical NLP baselines, keyword extraction, clustering, topic modeling, and embedding-based unsupervised analysis.",
                    "* Later sessions move through Word2Vec and the path from recurrent sequence models to transformer architectures.",
                    "* Recent iterations focus on BERT, sentence embeddings, prompt-based LLM use, and applied retrieval-augmented systems with real tradeoffs.",
                    "* Coursework typically includes several exercises plus a final project or project presentation.",
                ]
            ),
        },
    },
}

COMPACT_CONCRETE_SYLLABUS_CONTENT: dict[str, dict[str, object]] = {
    "data-vis": {
        "paragraph": (
            "This semester covers the full workflow of data visualization: understanding audience and task, "
            "choosing the right abstractions and chart forms, building dashboards in Tableau, and critiquing "
            "visual choices so that data stories stay both accurate and readable."
        ),
        "lectures": [
            ("1", "Course framing and intro to data visualization", "Why visualization matters, examples, and course structure."),
            ("2", "Task and data abstraction", "Turning messy analytical questions into formal visual tasks and data types."),
            ("3", "Marks, channels, and chart grammar", "How visual encodings shape readability and interpretation."),
            ("4", "Chart families and design tradeoffs", "Selecting chart types and avoiding misleading comparisons."),
            ("5", "Data preparation and Tableau workflows", "Preparing data and implementing visual ideas in Tableau."),
            ("6", "Dashboards, interaction, and storytelling", "Combining views into coherent dashboards and data-driven narratives."),
        ],
    },
    "deep-learning": {
        "paragraph": (
            "This semester treats deep learning as a practical modeling course: students build and train models in "
            "PyTorch, learn the major neural architectures used for images, text, and sequences, and finish with "
            "modern transformer and generative modeling topics."
        ),
        "lectures": [
            ("1", "Neural network foundations", "Backpropagation, optimization, and the practical training loop."),
            ("2", "Deep feedforward networks", "Regularization, stabilization, and deeper model design."),
            ("3", "Convolutional neural networks", "Image modeling, feature hierarchies, and transfer learning basics."),
            ("4", "Sequence models and attention", "RNNs, LSTMs, GRUs, and why transformers became dominant."),
            ("5", "Transformers and large-scale deep learning", "Modern architectures, pretrained models, and scaling ideas."),
            ("6", "Generative modeling and projects", "Autoencoders, VAEs, GANs, diffusion, and the final project path."),
        ],
    },
}

CONCRETE_COURSE_SUMMARY_TEMPLATES: dict[str, str] = {
    "data-vis": (
        "This semester of Data Visualization focused on visual reasoning, chart design, "
        "dashboard construction, and applied storytelling with data using Tableau and "
        "iterative critique."
    ),
    "deep-learning": (
        "This semester of Deep Learning focused on practical neural-network modeling in "
        "PyTorch, from optimization and core architectures through sequence models, "
        "transformers, and modern generative methods."
    ),
    "text-mining": (
        "This semester of Text Mining focused on practical NLP workflows, from preprocessing "
        "and classical representations through embeddings, transformers, and LLM-based "
        "applications."
    ),
    "econml": (
        "This semester of Intro to ML @ MTA focused on applied machine-learning thinking for "
        "economics and management students, with concrete predictive tasks, evaluation, and "
        "real-world business-style examples."
    ),
}

GENERIC_SUMMARY_PATTERN = re.compile(r"^Teaching materials extracted from Google Drive folder '.*'\.$")


def apply_generalized_course_content(course: Course) -> Course:
    if not course.is_generalized or not course.course_family:
        return course
    content = GENERALIZED_COURSE_CONTENT.get(course.course_family)
    if content is None:
        return course

    manual_overrides = dict(course.manual_overrides)
    for key, value in dict(content.get("manual_overrides", {}) or {}).items():
        manual_overrides.setdefault(key, value)

    return replace(
        course,
        subtitle=str(content.get("subtitle", course.subtitle) or course.subtitle),
        summary=str(content.get("summary", course.summary) or course.summary),
        hero_note=str(content.get("hero_note", course.hero_note) or course.hero_note),
        manual_overrides=manual_overrides,
    )


def apply_concrete_course_content(course: Course) -> Course:
    if course.is_generalized or not course.course_family:
        return course
    template = CONCRETE_COURSE_SUMMARY_TEMPLATES.get(course.course_family)
    if template is None:
        return course
    if course.summary and not GENERIC_SUMMARY_PATTERN.fullmatch(course.summary.strip()):
        return course
    return replace(course, summary=template)


def compact_concrete_syllabus_content(course_family: str) -> dict[str, object] | None:
    return COMPACT_CONCRETE_SYLLABUS_CONTENT.get(course_family)
