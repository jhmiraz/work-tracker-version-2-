words = input ("enter words seperated with white-space: ").split()
words=[word.lower() for word in words]

sorted_words = sorted(words)
print(f"sorted words: {sorted_words}")

search_word=input("enter a word to search: ")
found=False
for index,i in sorted_words:
    if i == search_word:
        print(f"found {search_word} at index {index}")
        found= True
        break
if not found:
    print(f"the searched word {search_word} isnt in input string")
