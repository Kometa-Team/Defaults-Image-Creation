"""
Grayscale Image Copier

This script copies grayscale images from a specified input directory to a "Downloads" directory. It uses the Python Imaging Library (PIL) to determine the image mode and copy the images.

Usage:
    python script_name.py -input_directory /path/to/images

Dependencies:
    - Python 3.x
    - PIL (Python Imaging Library)

"""

import os
import shutil
import datetime
from PIL import Image
import requests


def write_to_log_file(message):
    """Append a timestamped message to the script log file."""
    with open(script_log, 'a', encoding='utf-8') as log_file:
        log_file.write(f'{datetime.datetime.now()} ~ {message}\n')
    print(f'{datetime.datetime.now()} ~ {message}')


def write_to_download_log(message):
    """Append a timestamped message to the download log file."""
    with open(download_log, 'a', encoding='utf-8') as log_file:
        log_file.write(f'{datetime.datetime.now()} ~ {message}\n')
    print(f'{datetime.datetime.now()} ~ {message}')


def extract_filenames_from_source_directory(directory):
    """
    Extract filenames from the source directory.

    Args:
        directory (str): Path to the source directory.

    Returns:
        set: Set of file names extracted from the source directory.
    """
    file_names = set()
    for root, _, files in os.walk(directory):
        for filename in files:
            name, _ = os.path.splitext(filename)
            file_names.add(name)
    return file_names


def copy_file(source, destination):
    """Copy a file from the source path to the destination path."""
    shutil.copyfile(source, destination)
    write_to_log_file(f'Copied file from {source} => Saved as: {destination}')


def determine_image_mode(image_path):
    """
    Determine the mode of an image file.

    This function opens the image using PIL, converts it to RGB mode, and analyzes the pixel values. If the difference
    between the RGB channel values exceeds a predefined threshold, the image is considered to be in RGB mode.
    Otherwise, it is considered grayscale.

    Args:
        image_path (str): The path to the image file.

    Returns:
        str: 'RGB' if the image is in RGB mode, 'Grayscale' if it is in grayscale mode.
    """
    image = Image.open(image_path)
    image = image.convert('RGB')  # Convert to RGB mode to ensure consistent channel analysis
    pixels = image.getdata()
    channels = image.split()

    r_values = channels[0].getdata()
    g_values = channels[1].getdata()
    b_values = channels[2].getdata()

    color_variation_threshold = 30  # Adjust this threshold based on your requirements

    for r, g, b in zip(r_values, g_values, b_values):
        if abs(r - g) > color_variation_threshold or abs(r - b) > color_variation_threshold or abs(g - b) > color_variation_threshold:
            return 'RGB'

    return 'Grayscale'


def is_image_file(file_path):
    """
    Check if a file is an image file.

    This function attempts to open the file using PIL. If the file cannot be opened due to an IO or OS error,
    it is assumed not to be an image file.

    Args:
        file_path (str): The path to the file.

    Returns:
        bool: True if the file is an image file, False otherwise.
    """
    try:
        Image.open(file_path)
        return True
    except (IOError, OSError):
        return False


def fetch_online_file_names(online_url):
    """
    Fetch file names from an online URL.

    Args:
        online_url (str): The URL where file names are listed.

    Returns:
        set: Set of file names extracted from the online URL.
    """
    response = requests.get(online_url)
    if response.status_code != 200:
        print(f"Failed to fetch file names from the online URL: {online_url}")
        return set()

    # Extract file names from the response content
    file_names = set(response.text.split())
    return file_names


def copy_grayscale_and_color_images(directory, online_file_names, source_file_names):
    """
    Copy grayscale and color images from a directory to their respective download directories,
    excluding files whose names are found in the online file names list.

    Args:
        directory (str): The path to the input directory containing the images.
        online_file_names (set): Set of file names to exclude from copying.
        source_file_names (set): Set of file names in the source directory to compare for exclusion.
    """
    for root, _, files in os.walk(directory):
        for filename in files:
            name, _ = os.path.splitext(filename)

            # Skip copying the file if its name (without extension) is found online
            if name in online_file_names:
                print(f"File {filename} found in the online list. Skipping.")
                os.remove(os.path.join(root, filename))
                continue

            file_path = os.path.join(root, filename)
            if is_image_file(file_path):
                image_mode = determine_image_mode(file_path)
                if image_mode == 'Grayscale':
                    collection_name, _ = os.path.splitext(filename)
                    new_file_name = os.path.join(other_download_dir, collection_name + ".jpg")
                    copy_file(file_path, new_file_name)
                    write_to_download_log(f'Grayscale Image Copied: {filename} => Saved as: {new_file_name}')
                else:
                    collection_name, _ = os.path.splitext(filename)
                    new_file_name = os.path.join(color_download_dir, collection_name + ".jpg")
                    copy_file(file_path, new_file_name)
                    write_to_download_log(f'Color Image Copied: {filename} => Saved as: {new_file_name}')


def copy_grayscale_and_color_images2(directory, online_file_names):
    """
    Copy grayscale and color images from a directory to their respective download directories,
    excluding files whose names are found in the online file names list.

    Args:
        directory (str): The path to the input directory containing the images.
        online_file_names (set): Set of file names to exclude from copying.
    """
    for root, _, files in os.walk(directory):
        for filename in files:
            if filename in online_file_names:
                # Skip copying the file if its name is found online
                print(f"File {filename} found in the online list. Skipping.")
                os.remove(os.path.join(root, filename))
                continue

            file_path = os.path.join(root, filename)
            if is_image_file(file_path):
                image_mode = determine_image_mode(file_path)
                if image_mode == 'Grayscale':
                    collection_name, _ = os.path.splitext(filename)
                    new_file_name = os.path.join(other_download_dir, collection_name + ".jpg")
                    copy_file(file_path, new_file_name)
                    write_to_download_log(f'Grayscale Image Copied: {filename} => Saved as: {new_file_name}')
                else:
                    collection_name, _ = os.path.splitext(filename)
                    new_file_name = os.path.join(color_download_dir, collection_name + ".jpg")
                    copy_file(file_path, new_file_name)
                    write_to_download_log(f'Color Image Copied: {filename} => Saved as: {new_file_name}')


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Grayscale Image Copier')
    parser.add_argument('--input_directory', metavar='input_directory', type=str,
                        help='Specify the input directory containing images')

    args = parser.parse_args()

    input_directory = args.input_directory

    if not input_directory or not os.path.exists(input_directory):
        print(f'Input directory "{input_directory}" not found. Exiting now...')
        exit()

    script_path = os.path.dirname(os.path.realpath(__file__))
    script_name = os.path.basename(__file__)
    script_log = os.path.join(script_path, f'{script_name}.log')
    download_log = os.path.join(script_path, f'{script_name}_downloads.log')
    download_dir = os.path.join(script_path, 'Downloads')

    if os.path.exists(script_log):
        os.remove(script_log)

    write_to_log_file("#### START ####")

    os.makedirs(download_dir, exist_ok=True)

    # Add these lines to create 'Downloads\other' and 'Downloads\color' directories
    other_download_dir = os.path.join(script_path, 'Downloads', 'other')
    color_download_dir = os.path.join(script_path, 'Downloads', 'color')
    os.makedirs(other_download_dir, exist_ok=True)
    os.makedirs(color_download_dir, exist_ok=True)

    # Fetch online content and extract file names
    online_file_url = "https://raw.githubusercontent.com/Kometa-Team/People-Images-rainier/master/README.md"
    response = requests.get(online_file_url)
    if response.status_code != 200:
        print(f"Failed to fetch online content from the URL: {online_file_url}")
        exit()

    online_content = response.text
    online_file_names = online_content

    # Extract file names from the source directory
    source_file_names = extract_filenames_from_source_directory(input_directory)

    # Modify the function call to use copy_grayscale_and_color_images with online_file_names
    # and source_file_names
    copy_grayscale_and_color_images(input_directory, online_file_names, source_file_names)

    write_to_log_file("#### END ####")
