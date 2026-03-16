import os

from app.src.codetools.codetools import FileContentsSearchConfig, generate_file_trees
from app.src.codetools.merge import merge_code_from_files


def main():
    root_folder = "/path/to/your/project"
    search_terms = ["request.", "ap1.datadoghq.com"]

    # Create a SearchConfig with the search terms
    search_config = FileContentsSearchConfig(contains=search_terms)

    # Generate file trees using the search configuration
    all_files, all_folders, matching_files_all, matching_folders_all = generate_file_trees(
        root_folder, search_config
    )

    # Note: The above replaces the previous loop that processed each term separately.
    # The new SearchConfig approach allows searching for multiple terms in a single pass,
    # which is more efficient than the previous approach of searching for each term separately.

    # Convert sets back to sorted lists
    matching_files_all = sorted(matching_files_all)
    matching_folders_all = sorted(matching_folders_all)
    all_files = sorted(all_files)
    all_folders = sorted(all_folders)

    # Merge code from files
    merged_output = merge_code_from_files(
        matching_files_all,
        root_folder,
        include_file_tree=True,
        folder_tree=matching_folders_all,
        include_line_numbers=True,
    )

    # Save the merged output to a file
    output_file_path = os.path.join("llmmerge.txt")
    with open(output_file_path, "w") as output_file:
        output_file.write(merged_output)


if __name__ == "__main__":
    main()
