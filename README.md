![Image Banner](https://github.com/792x/HDR-Plus-Python/blob/master/Examples/Banner.png)

# HDR Plus Python
Implementation with GUI for desktop of Google's HDR+ in Python using Halide bindings. 

This repository is provided as is and is not maintained.

For our whitepaper see [https://github.com/792x/HDR-Plus-Python/blob/master/HDRPlus2020.pdf](https://github.com/792x/HDR-Plus-Python/blob/master/HDRPlus2020.pdf)

For the original paper see [https://www.hdrplusdata.org/hdrplus.pdf](https://www.hdrplusdata.org/hdrplus.pdf)

## Data
This project uses the [HDR+ Burst Photography Dataset](http://www.hdrplusdata.org/dataset.html).
To download the subset of bursts used in this project, download the [Google Cloud SDK](https://cloud.google.com/sdk/docs/#install_the_latest_cloud_sdk_version) and use the following command:
```
gsutil -m cp -r gs://hdrplusdata/20171106_subset .
```

## Prerequisites
- python 3.10.x: `conda create -n hdrplus python=3.10`
- `pip install -r requirements.txt`

## Examples
Input            |  Output
:-------------------------:|:-------------------------:
![Image Flowers_In](https://github.com/792x/HDR-Plus-Python/blob/master/Examples/flowers_in.jpg)  |  ![Image Flowers Out](https://github.com/792x/HDR-Plus-Python/blob/master/Examples/flowers_out.jpg)
![Image Chairs In](https://github.com/792x/HDR-Plus-Python/blob/master/Examples/chairs_input.jpg)  |  ![Image Chairs Out](https://github.com/792x/HDR-Plus-Python/blob/master/Examples/chairs_output.jpg)
![Image Sunflower In](https://github.com/792x/HDR-Plus-Python/blob/master/Examples/input_sunflower.jpg)  |  ![Image Sunflower Out](https://github.com/792x/HDR-Plus-Python/blob/master/Examples/output_sunflower.jpg)

## Graphical User Interface
![Image GUI](https://github.com/792x/HDR-Plus-Python/blob/master/Examples/empty_gui_v2.png)
![Image GUI Progress Bar](https://github.com/792x/HDR-Plus-Python/blob/master/Examples/progress_bar.png)


## Footnote
This project was inspired by [https://github.com/timothybrooks/hdr-plus](https://github.com/timothybrooks/hdr-plus)

