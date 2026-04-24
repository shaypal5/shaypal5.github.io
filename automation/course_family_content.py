from __future__ import annotations

from dataclasses import replace

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
