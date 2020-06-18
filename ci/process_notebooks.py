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

    if args.checkonly:
        exit(errors)

    # TODO should we exit here if there are errors?

    # Check compliancy with PEP8, generate a report, but don't fail on issues

    # TODO Check notebook name format?

    # Save the full version of the notebook, which contains solutions
    for nb_path, nb in notebooks.items():

        nb_dir, nb_fname = os.path.split(nb_path)

        # TODO only save out a solutions notebook if some solutions exist?

        # Create subdirectories, if they don't exist
        solutions_dir = make_sub_dir(nb_dir, "solutions")
        static_dir = make_sub_dir(nb_dir, "static")

        # Write the full notebook (TA verison) to the solutions directory
        solutions_path = os.path.join(solutions_dir, nb_fname)
        print(f"Writing TA notebook to {solutions_path}")
        with open(solutions_path, "w") as f:
            nbformat.write(nb, f)

        # Remove solutions and write the student version of the notebook
        remove_solutions(nb_path, nb, static_dir)

    exit(errors)


def remove_solutions(nb_path, nb, static_dir="static"):
    """Convert solution cells to markdown; embed images from Python output."""
    print(f"Removing solutions from {nb_path}")

    # Extract image data from the cell outputs
    c = Config()
    template = "static/solution_hint_{cell_index}_{index}{extension}"
    c.ExtractOutputPreprocessor.output_filename_template = template

    exporter = RSTExporter()
    extractor = ExtractOutputPreprocessor(config=c)
    exporter.register_preprocessor(extractor, True)
    _, resources = exporter.from_notebook_node(nb)

    # Convert solution cells to markdown with embedded image
    outputs = resources["outputs"]
    solution_outputs = {}

    nb_cells = nb.get("cells", [])
    for i, cell in enumerate(nb_cells):
        cell_text = cell["source"].replace(" ", "").lower()
        if cell_text.startswith("#@titlesolution"):

            if not cell["outputs"]:
                nb_cells.remove(cell)
                continue

            # Filter the resources for solution images
            image_paths = [k for k in outputs if f"solution_hint_{i}" in k]
            solution_outputs.update({k: outputs[k] for k in image_paths})

            # Embed the image (as a link to static resource) in markdown cell
            new_source = "**Example output:**\n\n" + "\n\n".join([
                f"<img src='{f}' align='left'>" for f in image_paths
            ])
            cell["source"] = new_source
            cell["cell_type"] = "markdown"
            del cell["outputs"]
            del cell["execution_count"]

    # Write the static files
    for fname, imdata in solution_outputs.items():
        fname = fname.replace("static", static_dir)
        with open(fname, "wb") as f:
            f.write(imdata)

    # Write the processed notebook back out to the original path
    with open(nb_path, "w") as f:
        nbformat.write(nb, f)


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
