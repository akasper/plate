param(
    [int]$Limit = 20
)

if ($Limit -lt 1) {
    Write-Error "Limit must be at least 1."
    exit 1
}

gh issue list --state open --limit $Limit --json number,title,labels,url --jq '.[] | select(any(.labels[]?; .name == "Question" or .name == "#question")) | "\(.number)\t\(.title)\t\(.url)"'
