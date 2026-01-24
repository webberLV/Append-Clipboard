Windows Registry Editor Version 5.00

; === APPEND TO CLIPBOARD ===

; For multiple file selection
[HKEY_CLASSES_ROOT\*\shell\AppendToClipboard]
@="Append to Clipboard"
"MultiSelectModel"="Player"
"Position"="Bottom"

[HKEY_CLASSES_ROOT\*\shell\AppendToClipboard\command]
@="\"C:\\Users\\web\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe\" \"C:\\Users\\web\\clipboard_context.py\" append %*"

; For folders
[HKEY_CLASSES_ROOT\Directory\shell\AppendToClipboard]
@="Append Folder to Clipboard"
"Position"="Bottom"

[HKEY_CLASSES_ROOT\Directory\shell\AppendToClipboard\command]
@="\"C:\\Users\\web\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe\" \"C:\\Users\\web\\clipboard_context.py\" append \"%1\""

; For folder background (right-click inside folder)
[HKEY_CLASSES_ROOT\Directory\Background\shell\AppendToClipboard]
@="Append Current Folder to Clipboard"
"Position"="Bottom"

[HKEY_CLASSES_ROOT\Directory\Background\shell\AppendToClipboard\command]
@="\"C:\\Users\\web\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe\" \"C:\\Users\\web\\clipboard_context.py\" append \"%V\""

; === REPLACE CLIPBOARD ===

; For multiple file selection
[HKEY_CLASSES_ROOT\*\shell\ReplaceClipboard]
@="Replace Clipboard"
"MultiSelectModel"="Player"
"Position"="Bottom"

[HKEY_CLASSES_ROOT\*\shell\ReplaceClipboard\command]
@="\"C:\\Users\\web\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe\" \"C:\\Users\\web\\clipboard_context.py\" replace %*"

; For folders
[HKEY_CLASSES_ROOT\Directory\shell\ReplaceClipboard]
@="Replace Clipboard with Folder"
"Position"="Bottom"

[HKEY_CLASSES_ROOT\Directory\shell\ReplaceClipboard\command]
@="\"C:\\Users\\web\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe\" \"C:\\Users\\web\\clipboard_context.py\" replace \"%1\""

; For folder background
[HKEY_CLASSES_ROOT\Directory\Background\shell\ReplaceClipboard]
@="Replace Clipboard with Current Folder"
"Position"="Bottom"

[HKEY_CLASSES_ROOT\Directory\Background\shell\ReplaceClipboard\command]
@="\"C:\\Users\\web\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe\" \"C:\\Users\\web\\clipboard_context.py\" replace \"%V\""