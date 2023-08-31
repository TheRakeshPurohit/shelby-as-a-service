import re
import string
from urllib.parse import urlparse
import shutil
import os
import json
from typing import List
import tiktoken
import spacy


class TextProcessing:
    @staticmethod
    def tiktoken_len(document):
        tokenizer = tiktoken.encoding_for_model("text-embedding-ada-002")
        tokens = tokenizer.encode(document, disallowed_special=())
        return len(tokens)

    @staticmethod
    def strip_excess_whitespace(text):
        # Defines which chars can be kept; Alpha-numeric chars, punctionation, and whitespaces.
        # Remove bad chars
        text = re.sub(f"[^{re.escape(string.printable)}]", "", text)
        # Reduces any sequential occurrences of a specific whitespace (' \t\n\r\v\f') to just two of those specific whitespaces
        # Create a dictionary to map each whitespace character to its escape sequence (if needed)
        whitespace_characters = {
            " ": r" ",
            "\t": r"\t",
            "\n": r"\n",
            "\r": r"\r",
            "\v": r"\v",
            "\f": r"\f",
        }
        # Replace any sequential occurrences of each whitespace characters greater than 3 with just two
        for char, escape_sequence in whitespace_characters.items():
            pattern = escape_sequence + "{3,}"
            replacement = char * 2
            text = re.sub(pattern, replacement, text)

        text = text.strip()

        return text

    @staticmethod
    def remove_all_white_space_except_space(text):
        # Remove all whitespace characters (like \n, \r, \t, \f, \v) except space (' ')
        text = re.sub(r"[\n\r\t\f\v]+", "", text)
        # Remove any extra spaces
        text = re.sub(r" +", " ", text)
        # Remove leading and trailing spaces
        text = text.strip()
        return text

    @staticmethod
    def remove_starting_whitespace_and_double_newlines(text):
        # Remove all starting whitespace characters (like \n, \r, \t, \f, \v, and ' ')
        text = re.sub(r"^[\n\r\t\f\v ]+", "", text)
        # Remove starting consecutive newline characters (\n\n)
        text = re.sub(r"^\n\n+", "", text)
        return text

    @staticmethod
    def split_text_with_regex(
        text: str, separator: str, keep_separator: bool
    ) -> List[str]:
        # Now that we have the separator, split the text
        if separator:
            if keep_separator:
                # The parentheses in the pattern keep the delimiters in the result.
                _splits = re.split(f"({separator})", text)
                splits = [
                    _splits[i] + _splits[i + 1] for i in range(1, len(_splits), 2)
                ]
                if len(_splits) % 2 == 0:
                    splits += _splits[-1:]
                splits = [_splits[0]] + splits
            else:
                splits = re.split(separator, text)
        else:
            splits = list(text)
        return [s for s in splits if s != ""]


class DFSTextSplitter:
    """Splits text that attempts to split by paragraph, newlines, sentences, and then spaces.
    Splits with regex for all but sentences.
    It then tries to construct chunks with the splits that fall within the token limits.
    Tiktoken is used as a tokenizer.
    After splitting, creating the chunks is used with a DFS algo utilizing memoization and a heuristic prefilter.
    """

    def __init__(
        self,
        goal_length,
        max_length,
        chunk_overlap,
        print_and_log,
    ) -> None:
        self.print_and_log = print_and_log
        self._separators = ["\n\n", "\n", "spacy_sentences"]
        # self._separators = ["\n\n", "\n", "spacy_sentences", " ", ""]
        self.spacy_sentences = spacy.load("en_core_web_sm")
        self._keep_separator: bool = True
        self.tiktoken_len = TextProcessing.tiktoken_len
        self.memo = {}
        self.goal_length = goal_length
        self.max_length = max_length or int(self.goal_length * 1.25)
        self.threshold_modifier = 0.2

        if not chunk_overlap or chunk_overlap < 100:
            chunk_overlap = 100
        self.chunk_overlap = chunk_overlap
        self.goal_length_max_threshold = goal_length + int(
            self.threshold_modifier * goal_length
        )
        self.goal_length_min_threshold = goal_length - int(
            self.threshold_modifier * goal_length
        )
        self.chunk_overlap_max_threshold = chunk_overlap + int(
            self.threshold_modifier * chunk_overlap
        )
        self.chunk_overlap_min_threshold = chunk_overlap - int(
            self.threshold_modifier * chunk_overlap
        )
        self.average_range_min = None

    def _split_text(self, text, separators, goal_length=None) -> List[List[str]]:
        """Handles splitting and chunking text.
        Recursively tries splitting methods until it finds one that works.
        """

        # Have to define here initially so it can be redefined for each recursion
        if goal_length is None:
            goal_length = self.goal_length
        # Get appropriate separator to use
        separator = separators[-1]
        new_separators = []
        for i, _s in enumerate(separators):
            # if _s == "":
            if _s == "spacy_sentences":
                separator = _s
                break
            # if _s == "spacy_sentences":
            #     separator = "spacy_sentences"
            #     new_separators = separators[i + 1 :]
            #     break
            elif re.search(_s, text):
                separator = _s
                new_separators = separators[i + 1 :]
                break

        # self.print_and_log(f"Trying separator: {repr(separator)} with goal_length: {goal_length}")

        # Use the current separator to split the text
        if separator == "spacy_sentences":
            doc = self.spacy_sentences(text)
            splits = [sent.text for sent in doc.sents]
        else:
            splits = TextProcessing.split_text_with_regex(
                text, separator, self._keep_separator
            )

        potential_chunks = self._find_valid_chunk_combinations(splits)
        if potential_chunks is None:
            if len(new_separators) > 0:
                potential_chunks = self._split_text(text, new_separators)

        return potential_chunks

    def _find_valid_chunk_combinations(self, splits):
        """Initializes the chunk combo finding process."""
        for split in splits:
            if self.tiktoken_len(split) > self.max_length:
                # self.print_and_log(
                #     f"Split '{split}' has length greater than max_length. Exiting early."
                # )
                return None
        self.memo = {}
        total_tokens = self.tiktoken_len("".join(splits))
        average_split_length = total_tokens / len(splits)
        self.average_range_min = int(
            (
                (self.goal_length_min_threshold - self.chunk_overlap_min_threshold)
                / average_split_length
            )
        )

        chunks_as_splits = self._recursive_chunk_tester(0, splits)

        if chunks_as_splits is None or not chunks_as_splits:
            # self.print_and_log("No valid chunk combinations found.")
            return None

        return chunks_as_splits

    def _recursive_chunk_tester(self, start, splits):
        """Manages the testing of chunk combonations.
        Stops when it successfuly finds a path to the final split.
        """
        valid_ends = self._find_valid_endsplits_for_start(start, splits)
        if not valid_ends:
            return None

        for end_split, overlap_split in valid_ends.items():
            if overlap_split + 1 == len(splits):
                # self.print_and_log(f"Returning chunk: splits[{start}:{overlap_split}]")
                output = "".join(splits[start : overlap_split + 1])
                output = TextProcessing.remove_starting_whitespace_and_double_newlines(
                    output
                )
                # self.print_and_log(f"Token count: {self.tiktoken_len(output)}")
                return [output]

        for end_split, overlap_split in valid_ends.items():
            # Check if the next start is out of bounds
            if overlap_split + 1 > len(splits):
                continue

            # Recursive call with the next start
            next_chunk = self._recursive_chunk_tester(end_split, splits)

            # If a valid combination was found in the recursive call
            if next_chunk is not None:
                # self.print_and_log(f"Returning chunk: splits[{start}:{overlap_split}]")
                output = "".join(splits[start : overlap_split + 1])
                output = TextProcessing.remove_starting_whitespace_and_double_newlines(
                    output
                )
                # self.print_and_log(f"Token count: {self.tiktoken_len(output)}")
                return [output] + next_chunk

        # If no valid chunking found for the current start, return None
        return None

    def _find_valid_endsplits_for_start(self, start, splits):
        """Returns endsplits that are within the threshold of goal_length.
        Uses memoization to save from having to recompute.
        Starts calculation at + self.average_range_min as a pre-filter.
        Returned endsplits include the maximum found chunk_overlap.
        """
        if start in self.memo:
            # self.print_and_log(f"Returning memoized result for start at index {start}")
            return self.memo[start]

        current_length = 0
        valid_ends = {}

        current_length = self.tiktoken_len(
            "".join(splits[start : start + self.average_range_min])
        )
        for j in range(start + self.average_range_min, len(splits)):
            # Failure break
            if j + 1 >= len(splits):
                break
            current_length += self.tiktoken_len(splits[j])
            if (
                current_length
                >= self.goal_length_min_threshold - self.chunk_overlap_min_threshold
            ):
                overlap_split = None
                overlap_length = 0
                k = j
                while (
                    k + 1 < len(splits)
                    and current_length + overlap_length
                    <= self.goal_length_max_threshold
                ):
                    k += 1
                    overlap_length += self.tiktoken_len(splits[k])
                    if (
                        self.goal_length_min_threshold
                        <= current_length + overlap_length
                        <= self.goal_length_max_threshold
                    ):
                        if self.chunk_overlap_min_threshold <= overlap_length:
                            # self.print_and_log(
                            #     f"valid_end {j} has valid overlap_split {k} with overlap_length {overlap_length}"
                            # )
                            overlap_split = k
                            if k + 1 == len(splits):
                                valid_ends[j] = overlap_split
                                # self.print_and_log(f"Start: {start} has valid_ends: {valid_ends}")
                                self.memo[start] = valid_ends
                                return valid_ends
                    else:
                        break
                if overlap_split:
                    valid_ends[j] = overlap_split

                if current_length >= self.goal_length_max_threshold:
                    break

        # self.print_and_log(f"Start: {start} has valid_ends: {valid_ends}")
        self.memo[start] = valid_ends
        return valid_ends

    def split_text(self, text) -> List[str]:
        """Interface for class."""
        return self._split_text(text, self._separators)


class BalancedRecursiveCharacterTextSplitter:
    """Implementation of splitting text that looks at characters.
    Recursively tries to split by different characters to find one that works. 
    Originally from Langchain's RecursiveCharacterTextSplitter.
    However this version retries if the chunk sizes does not meet the input requirements.
    """

    def __init__(
        self,
        goal_length,
        max_length,
        chunk_overlap,
        print_and_log,
    ) -> None:
        self.print_and_log = print_and_log
        self._separators = ["\n\n", "\n", "spacy_sentences", " ", ""]
        self.spacy_sentences = spacy.load("en_core_web_sm")
        self._keep_separator: bool = False
        self.goal_length = goal_length
        self.max_length = max_length or (self.goal_length * 1.25)
        self.tiktoken_len = TextProcessing.tiktoken_len
        # Chunk size logic
        if chunk_overlap is not None:
            # There must be at least some chunk overlap for this to function
            if chunk_overlap < 100:
                self._chunk_overlap = 100
            else:
                self._chunk_overlap = chunk_overlap
        else:
            self._chunk_overlap = self._chunk_overlap

    def _split_text(
        self, text: str, separators: List[str], goal_length=None
    ) -> List[List[str]]:
        """Split incoming text and return chunks."""

        # Have to define here initially so it can be redefined for each recursion
        if goal_length is None:
            goal_length = self.goal_length
        # Get appropriate separator to use
        separator = separators[-1]
        new_separators = []
        for i, _s in enumerate(separators):
            if _s == "":
                separator = _s
                break
            if _s == "spacy_sentences":
                separator = "spacy_sentences"
                new_separators = separators[i + 1 :]
                break
            elif re.search(_s, text):
                separator = _s
                new_separators = separators[i + 1 :]
                break

        # self.print_and_log(f"Trying separator: {repr(separator)} with goal_length: {goal_length}")

        # Use the current separator to split the text
        if separator == "spacy_sentences":
            doc = self.spacy_sentences(text)
            splits = [sent.text for sent in doc.sents]
        else:
            splits = TextProcessing.split_text_with_regex(
                text, separator, self._keep_separator
            )
        final_combos = self.distribute_splits(splits, goal_length)

        # If any split was larger than the max size
        # final_combos will be returned empty from distribute_splits
        if final_combos:
            for combo in final_combos:
                # If a combo of splits is too small,
                # we adjust the goal_length and retry separator
                combo_token_count = self.tiktoken_len("".join(combo))
                if (
                    combo_token_count < self.goal_length * 0.75
                    and len(final_combos) > 1
                ):
                    new_goal_length = int(
                        goal_length + (combo_token_count / (len(final_combos) - 1))
                    )
                    final_combos = self._split_text(text, separators, new_goal_length)
                # If a combo of splits is too large, we retry with new separator
                elif combo_token_count > self.max_length and new_separators:
                    final_combos = self._split_text(text, new_separators, goal_length)
        else:
            # In the case distribute_splits returned None continue to next separator
            final_combos = self._split_text(text, new_separators, goal_length)

        # All combos satisfy requirements
        return final_combos

    def distribute_splits(self, splits: list, goal_length: int) -> List[List[str]]:
        # Build initial combos
        combos: List[List[str]] = []
        current_combo = []
        combo_token_count = 0
        for split in splits:
            split_token_count = self.tiktoken_len(split)
            # If too big skip to next separator
            if split_token_count > self.max_length:
                combos = []
                return combos
            if goal_length > (combo_token_count + split_token_count):
                current_combo.append(split)
                combo_token_count = self.tiktoken_len("".join(current_combo))
            # Combo larger than goal_length
            else:
                current_combo.append(split)
                combos.append(current_combo)
                # Create a new combo and add the current split so there is overlap
                if split_token_count < self._chunk_overlap:
                    current_combo = []
                    current_combo.append(split)
                    combo_token_count = self.tiktoken_len("".join(current_combo))
                # If the overlap chunk is larger than overlap size
                # continue to next separator
                else:
                    combos = []
                    return combos
        # Add the last combo if it has more than just the overlap chunk
        if len(current_combo) > 1:
            combos.append(current_combo)
        return combos

    def split_text(self, text: str) -> List[str]:
        final_combos = self._split_text(text, self._separators, self.goal_length)
        return ["".join(combo) for combo in final_combos]


# Remove starting text whitespace/
class CEQTextPreProcessor:
    def __init__(self, data_source_config):
        self.index_agent = data_source_config.index_agent
        self.config = data_source_config.index_agent.config
        self.data_source_config = data_source_config
        self.print_and_log=self.index_agent.log.print_and_log
        self.tiktoken_encoding_model = self.config.index_tiktoken_encoding_model

        self.tiktoken_len = TextProcessing.tiktoken_len

        self.dfs_splitter = DFSTextSplitter(
            goal_length=self.config.index_text_splitter_goal_length,
            max_length=self.config.index_text_splitter_max_length,
            chunk_overlap=self.config.index_text_splitter_chunk_overlap,
            print_and_log=self.index_agent.log.print_and_log,
        )
        self.character_splitter = BalancedRecursiveCharacterTextSplitter(
            goal_length=self.config.index_text_splitter_goal_length,
            max_length=self.config.index_text_splitter_max_length,
            chunk_overlap=self.config.index_text_splitter_chunk_overlap,
            print_and_log=self.index_agent.log.print_and_log,
        )

    def run(self, documents) -> []:
        processed_document_chunks = []
        processed_text_chunks = []

        for i, doc in enumerate(documents):
            # If no doc title use the url and the resource type
            if not doc.metadata.get("title"):
                parsed_url = urlparse(doc.metadata.get("loc"))
                _, tail = os.path.split(parsed_url.path)
                # Strip anything with "." like ".html"
                root, _ = os.path.splitext(tail)
                doc.metadata[
                    "title"
                ] = f"{self.data_source_config.data_source_name}: {root}"

            # Remove bad chars and extra whitespace chars
            doc.page_content = TextProcessing.strip_excess_whitespace(doc.page_content)
            doc.metadata["title"] = TextProcessing.strip_excess_whitespace(
                doc.metadata["title"]
            )

            self.print_and_log(
                f"Preprocessing doc number: {i}\n Title: {doc.metadata['title']}"
            )

            # Skip if too small
            if (
                self.tiktoken_len(doc.page_content)
                < self.data_source_config.config.index_preprocessor_min_length
            ):
                self.print_and_log(
                    f"page too small: {self.tiktoken_len(doc.page_content)}"
                )
                continue

            # Split into chunks
            self.print_and_log(
                f"Splitting {doc.metadata['title']} with DFSTextSplitter"
                )
            text_chunks = self.dfs_splitter.split_text(doc.page_content)
            if text_chunks is None:
                self.print_and_log(
                    f"Splitting {doc.metadata['title']} with BalancedRecursiveCharacterTextSplitter"
                    )
                text_chunks = self.character_splitter.split_text(doc.page_content)
            if text_chunks is None:
                continue
            for text_chunk in text_chunks:
                document_chunk, text_chunk = self.append_metadata(text_chunk, doc)
                processed_document_chunks.append(document_chunk)
                processed_text_chunks.append(text_chunk.lower())

        self.print_and_log(f"Total docs: {len(documents)}")
        self.print_and_log(
            f"Total chunks: {len(processed_document_chunks)}"
        )
        if not processed_document_chunks:
            return
        token_counts = [self.tiktoken_len(chunk) for chunk in processed_text_chunks]
        self.print_and_log(f"Min: {min(token_counts)}")
        self.print_and_log(
            f"Avg: {int(sum(token_counts) / len(token_counts))}"
        )
        self.print_and_log(f"Max: {max(token_counts)}")
        self.print_and_log(f"Total tokens: {int(sum(token_counts))}")

        return processed_document_chunks

    def append_metadata(self, text_chunk, page):
        # Document chunks are the metadata uploaded to vectorstore
        document_chunk = {
            "content": text_chunk,
            "url": page.metadata["source"].strip(),
            "title": page.metadata["title"],
            "data_domain_name": self.data_source_config.data_domain_name,
            "data_source_name": self.data_source_config.data_source_name,
            "target_type": self.data_source_config.target_type,
            "doc_type": self.data_source_config.doc_type,
        }
        # Text chunks here are used to create embeddings
        text_chunk = f"{text_chunk} title: {page.metadata['title']}"

        return document_chunk, text_chunk

    def compare_chunks(self, data_source, document_chunks):
        folder_path = f"{self.index_agent.index_dir}/outputs/{data_source.data_domain_name}/{data_source.data_source_name}"
        # Create the directory if it does not exist
        os.makedirs(folder_path, exist_ok=True)
        existing_files = os.listdir(folder_path)
        has_changes = False
        # This will keep track of the counts for each title
        title_counter = {}
        # This will hold the titles of new or different chunks
        new_or_changed_chunks = []
        for document_chunk in document_chunks:
            sanitized_title = re.sub(r"\W+", "_", document_chunk["title"])
            text_chunk = f"{document_chunk['content']} title: {document_chunk['title']}"
            # Skip overly long chunks
            if (
                self.tiktoken_len(text_chunk)
                > self.config.index_text_splitter_max_length
            ):
                continue
            # Check if we've seen this title before, if not initialize to 0
            if sanitized_title not in title_counter:
                title_counter[sanitized_title] = 0
            file_name = f"{sanitized_title}_{title_counter[sanitized_title]}.json"
            # Increment the counter for this title
            title_counter[sanitized_title] += 1
            if file_name not in existing_files:
                has_changes = True
                new_or_changed_chunks.append(document_chunk["title"])
            else:
                existing_file_path = os.path.join(folder_path, file_name)
                with open(existing_file_path, "r") as f:
                    existing_data = json.load(f)
                    if existing_data != document_chunk:
                        has_changes = True
                        new_or_changed_chunks.append(document_chunk["title"])

        return has_changes, new_or_changed_chunks

    def create_text_chunks(self, data_source, document_chunks):
        checked_document_chunks = []
        checked_text_chunks = []
        # This will keep track of the counts for each title
        title_counter = {}
        for document_chunk in document_chunks:
            sanitized_title = re.sub(r"\W+", "_", document_chunk["title"])
            # Check if we've seen this title before, if not initialize to 0
            if sanitized_title not in title_counter:
                title_counter[sanitized_title] = 0
            # Increment the counter for this title
            title_counter[sanitized_title] += 1
            text_chunk = f"{document_chunk['content']} title: {document_chunk['title']}"
            # Skip overly long chunks
            if (
                self.tiktoken_len(text_chunk)
                > self.config.index_text_splitter_max_length
            ):
                continue
            checked_document_chunks.append(document_chunk)
            checked_text_chunks.append(text_chunk.lower())

        return checked_text_chunks, checked_document_chunks

    def write_chunks(self, data_source, document_chunks):
        folder_path = f"{self.index_agent.index_dir}/outputs/{data_source.data_domain_name}/{data_source.data_source_name}"
        # Clear the folder first
        shutil.rmtree(folder_path)
        os.makedirs(folder_path, exist_ok=True)
        # This will keep track of the counts for each title
        title_counter = {}
        for document_chunk in document_chunks:
            sanitized_title = re.sub(r"\W+", "_", document_chunk["title"])
            text_chunk = f"{document_chunk['content']} title: {document_chunk['title']}"
            # Skip overly long chunks
            if (
                self.tiktoken_len(text_chunk)
                > self.config.index_text_splitter_max_length
            ):
                continue
            # Check if we've seen this title before, if not initialize to 0
            if sanitized_title not in title_counter:
                title_counter[sanitized_title] = 0
            file_name = f"{sanitized_title}_{title_counter[sanitized_title]}.json"
            # Increment the counter for this title
            title_counter[sanitized_title] += 1
            file_path = os.path.join(folder_path, file_name)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(document_chunk, f, indent=4)
