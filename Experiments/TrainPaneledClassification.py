# ---
# jupyter:
#   jupytext:
#     formats: py:light
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.11.4
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

from argparse import ArgumentParser

import matplotlib.pyplot as plt
import os.path
from os import path

from fastai.vision.all import *
from fastai.callback.progress import CSVLogger
from torchvision import transforms

# Assign GPU
torch.cuda.set_device(2)
print("Running on GPU: " + str(torch.cuda.current_device()))

# Constants (same for all trials)
VALID_PCT = 0.05
NUM_REPLICATES = 4
NUM_EPOCHS = 8
DATASET_DIR = Path("/raid/clark/summer2021/datasets")
MODEL_PATH_REL_TO_DATASET = Path("paneled_models2")
DATA_PATH_REL_TO_DATASET = Path("paneled_data2")
VALID_MAZE_DIR = Path("../Mazes/validation_mazes8x8/")

compared_models = {
    "alexnet": alexnet,
    "xresnext50": xresnext50,
    "xresnext18": xresnext18,
    "densenet121": densenet121,
}

img_dir = Path("/raid/clark/summer2021/datasets/corrected-wander-full/")
img_filenames = list(img_dir.glob("*.png"))
img_filenames.sort()

def get_pair(o):
    curr_im_num = int(Path(o).name[:6])
    prev_im_num = curr_im_num if curr_im_num == 0 else curr_im_num - 1
    prev_im = img_filenames[prev_im_num]

    #print(curr_im_num, prev_im_num)
    #print(o, prev_im)
    
    img1 = Image.open(o).convert('RGB')
    img2 = Image.open(prev_im).convert('RGB')
    img1_t = transforms.ToTensor()(img1).unsqueeze_(0)
    img2_t = transforms.ToTensor()(img2).unsqueeze_(0)
    
    new_shape = list(img1_t.shape)
    new_shape[-2] = new_shape[-2] * 2
    img3_t = torch.zeros(new_shape)

    img3_t[:, :, :224, :] = img1_t
    img3_t[:, :, 224:, :] = img2_t
    
    img3 = transforms.ToPILImage()(img3_t.squeeze_(0))
    
    return np.array(img3)


def get_fig_filename(prefix: str, label: str, ext: str, rep: int) -> str:
    fig_filename = f"{prefix}-{label}-{rep}.{ext}"
    print(label, "filename :", fig_filename)
    return fig_filename


def filename_to_class(filename) -> str:
    angle = float(str(filename).split("_")[1].split(".")[0].replace("p", "."))
    if angle > 0:
        return "left"
    elif angle < 0:
        return "right"
    else:
        return "forward"


def prepare_dataloaders(dataset_name: str, prefix: str) -> DataLoaders:

    path = DATASET_DIR / dataset_name
    
    db = DataBlock(
        blocks=(ImageBlock, CategoryBlock),
        get_items=get_image_files,
        splitter=RandomSplitter(valid_pct=VALID_PCT),
        get_y=filename_to_class,
        get_x=get_pair
    )

    dls = db.dataloaders(path, bs=64)
    dls.show_batch()  # type: ignore
    plt.savefig(get_fig_filename(prefix, "batch", "pdf", 0))

    return dls  # type: ignore


def train_model(
    dls: DataLoaders,
    model_arch: str,
    pretrained: bool,
    logname: Path,
    modelname: Path,
    prefix: str,
    rep: int,
):
    learn = cnn_learner(
        dls,
        compared_models[model_arch],
        metrics=accuracy,
        pretrained=pretrained,
        cbs=CSVLogger(fname=logname),
    )

    if pretrained:
        learn.fine_tune(NUM_EPOCHS)
    else:
        learn.fit_one_cycle(NUM_EPOCHS)

    # The follwing line is necessary for pickling
    learn.remove_cb(CSVLogger)
    learn.export(modelname)
"""
    learn.show_results()
    plt.savefig(get_fig_filename(prefix, "results", "pdf", rep))

    interp = ClassificationInterpretation.from_learner(learn)
    interp.plot_top_losses(9, figsize=(15, 10))
    plt.savefig(get_fig_filename(prefix, "toplosses", "pdf", rep))

    interp.plot_confusion_matrix(figsize=(10, 10))
    plt.savefig(get_fig_filename(prefix, "confusion", "pdf", rep))"""


def main():

    arg_parser = ArgumentParser("Train paneled classification networks.")
    arg_parser.add_argument(
        "model_arch", help="Model architecture (see code for options)"
    )
    arg_parser.add_argument(
        "dataset_name", help="Name of dataset to use (handmade-full | corrected-wander-full)"
    )
    arg_parser.add_argument(
        "--pretrained", action="store_true", help="Use pretrained model"
    )

    args = arg_parser.parse_args()

    # TODO: not using this (would require replacing first layer)
    # rgb_instead_of_gray = True

    # Make dirs as needed
    model_dir = DATASET_DIR / args.dataset_name / MODEL_PATH_REL_TO_DATASET
    model_dir.mkdir(exist_ok=True)
    print(f"Created model dir (or it already exists) : '{model_dir}'")

    data_dir = DATASET_DIR / args.dataset_name / DATA_PATH_REL_TO_DATASET
    data_dir.mkdir(exist_ok=True)
    print(f"Created data dir (or it already exists)  : '{data_dir}'")

    file_prefix = "classification-" + args.model_arch
    # file_prefix += "-rgb" if rgb_instead_of_gray else "-gray"
    file_prefix += "-pretrained" if args.pretrained else "-notpretrained"
    fig_filename_prefix = data_dir / file_prefix

    dls = prepare_dataloaders(args.dataset_name, fig_filename_prefix)

    # Train NUM_REPLICATES separate instances of this model and dataset
    for rep in range(NUM_REPLICATES):
        
        model_filename = DATASET_DIR / args.dataset_name / MODEL_PATH_REL_TO_DATASET / f"{file_prefix}-{rep}.pkl"
        print("Model relative filename :", model_filename)

        # Checks if model exists and skip if it does (helps if this crashes)
        if path.exists(model_filename):
            continue

        log_filename = DATASET_DIR / args.dataset_name / DATA_PATH_REL_TO_DATASET / f"{file_prefix}-trainlog-{rep}.csv"
        print("Log relative filename   :", log_filename)

        train_model(
            dls,
            args.model_arch,
            args.pretrained,
            log_filename,
            model_filename,
            fig_filename_prefix,
            rep,
        )


if __name__ == "__main__":
    main()
