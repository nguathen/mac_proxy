on run
    set projectPath to POSIX path of ((path to me as string) & "::")
    set projectPath to text 1 thru -13 of projectPath
    set projectPath to projectPath & "mac_proxy"
    
    tell application "Terminal"
        activate
        do script "cd '" & projectPath & "' && ./launch_app.sh"
    end tell
end run

