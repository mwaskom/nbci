"""Process tutorials for Neuromatch Academy

- Excute .ipynb files and report any errors encountered
- Copy the original notebook to a "solutions" folder for TAs
- Remove inputs (but not outputs) from solution cells in original notebook

"""
import os
import sys
import argparse
import nbformat
from traitlets.config import Config
from nbconvert.exporters import RSTExporter
from nbconvert.preprocessors import (
    ExecutePreprocessor,
    ExtractOutputPreprocessor
)


def main(arglist):
    """Process IPython notebooks from a list of files."""
    args = parse_args(arglist)

    # Filter to only ipython notebook fikes
    nb_paths = [arg for arg in args.files if arg.endswith(".ipynb")]
    if not nb_paths:
        print("No notebook files found")
        sys.exit(0)

    # Allow environment to override stored kernel name
    exec_kws = {"timeout": 600}
    if "NB_KERNEL" in os.environ:
        exec_kws["kernel_name"] = os.environ["NB_KERNEL"]

    # Defer failures until after processing all notebooks
    errors = {}
    notebooks = {}

    for nb_path in nb_paths:

        # Load the notebook structure
        with open(nb_path) as f:
            nb = nbformat.read(f, nbformat.NO_CONVERT)

        # Run the notebook from top to bottom, catching errors
        print(f"Executing {nb_path}")
        executor = ExecutePreprocessor(**exec_kws)
        try:
            executor.preprocess(nb)
        except Exception as err:
            errors[nb_path] = err
        else:
            notebooks[nb_path] = nb

    if errors or args.checkonly:
        exit(errors)

    # TODO Check compliancy with PEP8, generate a report, but don't fail

    # TODO Check notebook name format?

    # Remove solution code from notebooks and write out a "student" version
    # TODO only save out a solutions notebook if some solutions exist?
    for nb_path, nb in notebooks.items():

        nb_dir, nb_fname = os.path.split(nb_path)

        # Create subdirectories, if they don't exist
        student_dir = make_sub_dir(nb_dir, "student")
        static_dir = make_sub_dir(nb_dir, "static")

        # Remove solutions and write the student version of the notebook
        print(f"Removing solutions from {nb_path}")
        student_nb, solution_resources = remove_solutions(nb)

        # Write the full notebook (TA verison) to the solutions directory
        student_nb_path = os.path.join(student_dir, nb_fname)
        print(f"Writing student notebook to {student_nb_path}")
        with open(student_nb_path, "w") as f:
            nbformat.write(student_nb, f)

        # Write the static files representing solutions for student notebooks
        print(f"Writing solution resources to {static_dir}")
        for fname, imdata in solution_resources.items():
            fname = fname.replace("../static", static_dir)
            with open(fname, "wb") as f:
                f.write(imdata)

        # TODO write out the executed version of the complete notebook?
        # I don't think we wnat to overwrite the incoming notebook, so
        # we should do this only if we have a "flat" organization

    exit(errors)


def remove_solutions(nb):
    """Convert solution cells to markdown; embed images from Python output."""

    # -- Extract image data from the cell outputs
    c = Config()
    template = "../static/solution_hint_{cell_index}_{index}{extension}"
    c.ExtractOutputPreprocessor.output_filename_template = template

    # Note: using the RST exporter means we need to install pandoc as a dep
    # in the github workflow, which adds a little bit of latency, and we don't
    # actually care about the RST output. It's just a convenient way to get the
    # image resources the way we want them.
    exporter = RSTExporter()
    extractor = ExtractOutputPreprocessor(config=c)
    exporter.register_preprocessor(extractor, True)
    _, resources = exporter.from_notebook_node(nb)

    # -- Convert solution cells to markdown with embedded image
    nb_cells = nb.get("cells", [])
    outputs = resources["outputs"]
    solution_resources = {}

    for i, cell in enumerate(nb_cells):
        cell_text = cell["source"].replace(" ", "").lower()
        if cell_text.startswith("#@titlesolution"):

            if not cell["outputs"]:
                nb_cells.remove(cell)
                continue

            # Filter the resources for solution images
            image_paths = [k for k in outputs if f"solution_hint_{i}" in k]
            solution_resources.update({k: outputs[k] for k in image_paths})

            # Embed the image (as a link to static resource) in markdown cell
            new_source = "**Example output:**\n\n" + "\n\n".join([
                f"<img src='{f}' align='left'>" for f in image_paths
            ])
            cell["source"] = new_source
            cell["cell_type"] = "markdown"
            del cell["outputs"]
            del cell["execution_count"]

    return nb, solution_resources


def make_sub_dir(nb_dir, name):

    sub_dir = os.path.join(nb_dir, name)
    if not os.path.exists(sub_dir):
        os.mkdir(sub_dir)
    return sub_dir


def exit(errors):
    """Exit with message and status dependent on contents of errors dict."""
    for failed_file, error in errors.items():
        print(f"{failed_file} did not execute cleanly.")
        print("Error message:", end="\n")
        print(error)

    status = bool(errors)
    if status:
        print("========== Failure ==========")
    else:
        print("========== Success ==========")
    sys.exit(status)


def parse_args(arglist):
    """Handle the command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Process neuromatch tutorial notebooks",
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="File name(s) to process. Will filter for .ipynb extension."
    )
    parser.add_argument(
        "--checkonly",
        action="store_true",
        help="Only check that the notebook can execute"
    )
    return parser.parse_args(arglist)


if __name__ == "__main__":

    main(sys.argv[1:])
