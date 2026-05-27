generate_cad_prototype_tool = {
    "name": "generate_cad_prototype",
    "description": "Generates a 3D wireframe prototype based on a user's description. Use this when the user asks to 'visualize', 'prototype', 'create a wireframe', or 'design' something in 3D.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "prompt": {
                "type": "STRING",
                "description": "The user's description of the object to prototype."
            }
        },
        "required": ["prompt"]
    }
}




write_file_tool = {
    "name": "write_file",
    "description": "Writes content to a file at the specified path. Overwrites if exists.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "path": {
                "type": "STRING",
                "description": "The path of the file to write to."
            },
            "content": {
                "type": "STRING",
                "description": "The content to write to the file."
            }
        },
        "required": ["path", "content"]
    }
}

read_directory_tool = {
    "name": "read_directory",
    "description": "Lists the contents of a directory.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "path": {
                "type": "STRING",
                "description": "The path of the directory to list."
            }
        },
        "required": ["path"]
    }
}

read_file_tool = {
    "name": "read_file",
    "description": "Reads the content of a file.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "path": {
                "type": "STRING",
                "description": "The path of the file to read."
            }
        },
        "required": ["path"]
    }
}

open_url_tool = {
    "name": "open_url",
    "description": "Opens a URL or website in the user's default browser. Use this when the user asks to 'open Google', 'go to YouTube', 'open a website', 'search for something on Google', etc. The website will open on the user's actual screen.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "url": {
                "type": "STRING",
                "description": "The URL to open. Can be a full URL, Google search 'search: query', or Youtube search 'ytsearch: query'."
            }
        },
        "required": ["url"]
    }
}

tools_list = [{"function_declarations": [
    generate_cad_prototype_tool,
    write_file_tool,
    read_directory_tool,
    read_file_tool,
    open_url_tool
]}]


