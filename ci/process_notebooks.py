"""Process tutorials for Neuromatch Academy

- Filter input file list for .ipynb files
- Check that the cells have been executed sequentially on a fresh kernel
- Execute the notebook and report any errors encountered
- Remove solution cells but retain any images they generated as static content
- Write the executed version of the input notebook to its original path
- Write the post-processed notebook to a student/ subdirectory
- Write solution images to a static/ subdirectory

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

        if not sequentially_executed(nb):
            if args.require_sequntial:
                errors[nb_path] = "Notebook is not sequentially executed."
                continue

        # Run the notebook from top to bottom, catching errors
        print(f"Executing {nb_path}")
        executor = ExecutePreprocessor(**exec_kws)
        try:
            executor.preprocess(nb)
        except Exception as err:
            errors[nb_path] = err
        else:
            notebooks[nb_path] = nb

    if errors or args.check_only:
        exit(errors)

    # TODO Check compliancy with PEP8, generate a report, but don't fail

    # TODO Check notebook name format?
    # (If implemented, update the CI workflow to only run on tutorials)

    # Remove solution code from notebooks and write out a "student" version
    for nb_path, nb in notebooks.items():

        nb_dir, nb_fname = os.path.split(nb_path)
        nb_name, _ = os.path.splitext(nb_fname)

        # Create subdirectories, if they don't exist
        student_dir = make_sub_dir(nb_dir, "student")
        static_dir = make_sub_dir(nb_dir, "static")

        # Generate the student version and save it to a subdirectory
        print(f"Removing solutions from {nb_path}")
        student_nb, solution_resources = remove_solutions(nb, nb_name)

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

        # Write out the executed version of the original notebook
        with open(nb_path, "w") as f:
            nbformat.write(nb, f)

    exit(errors)


def remove_solutions(nb, nb_name):
    """Convert solution cells to markdown; embed images from Python output."""

    # -- Extract image data from the cell outputs
    c = Config()
    template = (
        f"../static/{nb_name}"
        "_Solution_{cell_index}_{index}{extension}"
    )
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

            # Just remove solution cells that generate no outputs
            if not cell["outputs"]:
                nb_cells.remove(cell)
                continue

            # Filter the resources for solution images
            image_paths = [k for k in outputs if f"Solution_{i}" in k]
            solution_resources.update({k: outputs[k] for k in image_paths})

            # Conver the solution cell to markdown, strip the source,
            # and embed the image as a link to static resource
            new_source = "**Example output:**\n\n" + "\n\n".join([
                f"<img src='{f}' align='left'>" for f in image_paths
            ])
            cell["source"] = new_source
            cell["cell_type"] = "markdown"
            del cell["outputs"]
            del cell["execution_count"]

    return nb, solution_resources


def sequentially_executed(nb):
    """Return True if notebook appears freshly executed from top-to-bottom."""
    exec_counts = [
        cell["execution_count"]
        for cell in nb.get("cells", [])
        if (
            cell["source"]
            and cell.get("execution_count", None) is not None
        )
    ]
    sequential_counts = list(range(1, 1 + len(exec_counts)))
    # Returns True if there are no executed code cells, which is fine?
    return exec_counts == sequential_counts


def make_sub_dir(nb_dir, name):
    """Create nb_dir/name if it does not exist."""
    sub_dir = os.path.join(nb_dir, name)
    if not os.path.exists(sub_dir):
        os.mkdir(sub_dir)
    return sub_dir


def exit(errors):
    """Exit with message and status dependent on contents of errors dict."""
    for failed_file, error in errors.items():
        print(f"{failed_file} failed quality control.")
        print(error)

    status = bool(errors)
    report = "Failure" if status else "Success"
    print("=" * 30, report, "=" * 30)
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
        "--check-only",
        action="store_true",
        dest="check_only",
        help="Only run QC checks; don't do post-processing"
    )
    parser.add_argument(
        "--allow-non-sequential",
        action="store_false",
        dest="require_sequntial",
        help="Don't fail if the notebook is not sequentially executed"
    )
    return parser.parse_args(arglist)


if __name__ == "__main__":

    main(sys.argv[1:])
