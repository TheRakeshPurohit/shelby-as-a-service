web_base.py

def lazy_load(self) -> Iterator[Document]:
        """Lazy load text from the url(s) in web_path."""
        for path in self.web_paths:
            soup = self._scrape(path)
            # text = soup.get_text(**self.bs_get_text_kwargs)
            text_element = soup.find_all(id='content')[0]
            text = text_element.get_text()
            metadata = _build_metadata(soup, path)
            yield Document(page_content=text, metadata=metadata)
            
            
class BalancedRecursiveCharacterTextSplitter(TextSplitter):
    def __init__(
            self, 
            goal_length, 
            max_length, 
            separators: Optional[List[str]] = None, 
            keep_separator=True, 
            **kwargs: Any
            ):
        self.goal_length = goal_length
        self.max_length = max_length
        super().__init__(keep_separator=keep_separator, **kwargs)
        self._separators = separators or ["\n\n", "\n", " ", ""]

    def _split_text(self, text: str, separators: List[str], goal_length=None) -> List[str]:
        """Split incoming text and return chunks."""
        if goal_length is None:
            goal_length = self.goal_length
        # Get appropriate separator to use
        separator = separators[-1]
        new_separators = []
        for i, _s in enumerate(separators):
            if _s == "":
                separator = _s
                break
            if re.search(_s, text):
                separator = _s
                new_separators = separators[i + 1 :]
                break
        print(separator)
        # Use the current separator (sep) to split the text
        splits = _split_text_with_regex(text, separator, self._keep_separator)
        final_combos = self.distribute_splits(splits, goal_length)
        if final_combos:
            for combo in final_combos:
                print(self._length_function(''.join(combo)))
                combo_token_count = self._length_function(''.join(combo))
                # If a combo of splits is too small, we adjust the goal_length and retry separator
                if combo_token_count < self.goal_length * .75 and len(final_combos) > 1:
                    new_goal_length = goal_length + (combo_token_count / (len(final_combos) - 1))
                    # Recurse with adjusted goal_length
                    final_combos = self._split_text(text, separators, new_goal_length)
                # If no separators left to recurse exit
                elif combo_token_count > self.max_length and new_separators:
                    final_combos = self._split_text(text, new_separators)
        # If any split was larger than the max size final_combos will be empty
        else:
            # continue to next separator
            final_combos = self._split_text(text, new_separators)

        return final_combos
    
    def distribute_splits(self, splits, goal_length):
        # Build initial combos
        combos = []
        current_combo = []
        combo_token_count = 0
        for split in splits:
            split_token_count = self._length_function(split)
            # If too big skip to next separator
            if split_token_count > self.max_length:
                combos = []
                return combos
            if goal_length > (combo_token_count + split_token_count):
                current_combo.append(split)
                combo_token_count = self._length_function(''.join(current_combo))
            # Combo larger than goal_length
            else:
                current_combo.append(split)
                combos.append(current_combo)
                # Create a new combo and add the current split so there is overlap
                if split_token_count < self._chunk_overlap:
                    current_combo = []
                    current_combo.append(split)
                    combo_token_count = self._length_function(''.join(current_combo))
                # If the overlap chunk is larger than overlap size continue to next separator
                else:
                    combos = []
                    return combos
        # Add the last combo if it has more than just the overlap chunk
        if len(current_combo) > 1:
            combos.append(current_combo)
        return combos
        
    def split_text(self, text: str) -> List[str]:
        final_combos = self._split_text(text, self._separators)
        return [''.join(combo) for combo in final_combos]
