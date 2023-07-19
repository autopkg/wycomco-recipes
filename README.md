# wycomco-recipes

Public repository with [AutoPKG](https://github.com/autopkg) recipes by [wycomco](https://www.wycomco.de/?mtm_campaign=community-posts&mtm_source=github&mtm_content=autopkg-recipes-readme), an [Apple Consultant Network](https://consultants.apple.com) partner from [Berlin](https://maps.apple.com/?address=Berlin,%20Deutschland&auid=3539789365695356771&ll=52.517780,13.409839&lsp=7618&q=Berlin&_ext=CiAKBQgEEIEBCgQIBRADCgUIBhCCAQoECAoQAwoECFUQAhImKbtva8FBIEpAMUxRLo1fzClAOVf46S4/YkpAQfghJSzgzCtAUAw%3D).

If you like and use our recipes give us a ![Star](README-images/star.png) of appreciation.

## Installation

First install AutoPkg and git, then add this repo by:

```Shell
autopkg repo-add wycomco-recipes
```

## SharedProcessors

Currently we offer a handfull processors:

* [JamfMultiUploader](https://github.com/autopkg/wycomco-recipes/blob/master/SharedProcessors/JamfMultiUploader.py): Take the great [JamfUploader Processors](https://github.com/grahampugh/jamf-upload) from [Graham Pugh](https://grahamrpugh.com) to the next level and manage *multiple* Jamf Pro instances from a single recipe or override.
* [MunkiAutoStaging](https://github.com/autopkg/wycomco-recipes/blob/master/SharedProcessors/MunkiAutoStaging.py): Automatically promote Munki packages from a staging catalog to a production catalog, [here](https://medium.com/@choules/staging-munki-updates-with-autopkg-da58d2f79020) you may find a short introduction.
* [MunkiRepoTeamsNotifier](https://github.com/autopkg/wycomco-recipes/blob/master/SharedProcessors/MunkiRepoTeamsNotifier.py): Send a notification to a Microsoft Teams channel with information about recent changes in your Munki repository.

## Dependencies

Please be aware that some recipes might be dependent on other peoples fantastic work.

* DeepL: [autopkg/andredb90-recipes](https://github.com/autopkg/andredb90-recipes) `autopkg repo-add andredb90-recipes`
* MicrosoftOffice365: [autopkg/rtrouton-recipes](https://github.com/autopkg/rtrouton-recipes) `autopkg repo-add rtrouton-recipes`

## Issues

Before opening an issue please check if it already exists.
