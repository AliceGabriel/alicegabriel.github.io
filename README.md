# www.alicegabriel.com

The source of Alice-Agnes Gabriel's website. GitHub Pages turns these files into the site each time a change is saved to the `main` branch. There is nothing to install and nothing to run.

## Where things are

| To change | Edit |
| --- | --- |
| Home page: positions, the three videos, research interests, news | `index.md` |
| Team | `team.md` |
| Publications | `publications.md` |
| Projects | `projects.md` |
| About Me (CV, awards, service, talks) | `about-me.md` |
| In the media | `in-the-media.md` |
| Codes and HPC Training | `codes-and-hpc-training.md` |
| Teaching | `teaching.md` |
| The menu | `_data/nav.yml` |
| Pictures | `assets/img/` |
| Paper PDFs, CV | `assets/papers/`, `assets/files/` |
| Colours, fonts, spacing | `assets/css/site.css` |
| Page frame (header, footer) | `_layouts/default.html` |

Every page file starts with a settings block between two `---` lines. The text below it is Markdown.

To edit on github.com: open the file, press the pencil icon, change the text, press "Commit changes". The site updates within a minute or two.

## Common changes

### Add a news item

In `index.md`, paste a new block directly under the `## News` line:

```markdown
![](/assets/img/home/my-picture.jpg)

### Title of the news item

Text of the news item, with [a link](https://example.org).

***
```

The line with three asterisks separates news items. Keep an empty line above and below it. A news item can go without a picture.

### Add a publication

In `publications.md`, copy an existing line, paste it at the top of its year and edit it. One paper is one line that starts with `- `.

- Write the student and postdoc marker as `\*` (backslash, then asterisk). A plain `*` after a name turns the following text into italics.
- `**text**` is bold (your name, the title). `*text*` is italics (the journal).
- A PDF in this repository is linked as `**[[pdf](/assets/papers/file-name.pdf)]**`.

### Add a PDF or a picture

On github.com open the folder (`assets/papers/` or `assets/img/...`), then "Add file", "Upload files". Use file names without spaces. GitHub does not accept files of 100 MB or more.

### Add a team member

In `team.md`, add a line to the list it belongs to:

```markdown
- [**First Last**](https://their-website.org) (2026-, SIO)
```

### Add a project

In `projects.md`, copy an existing block (logo, `### Name`, one sentence, `[Read More](...)`) and the `***` line that separates it from its neighbour.

### Add a video

A video line needs the YouTube id, the part after `v=` in the video address:

```liquid
{% include video.html id="JpwcWkPuc9A" title="A Scientist's Life: Alice Gabriel" %}
```

The page shows a still picture. The video plays in place after a click, so nothing loads from YouTube's player before that.

The three videos at the top of the home page are listed in the settings block of `index.md` under `videos:`.

### Change the group photos on the Team page

They are listed in the settings block of `team.md` under `photos:`, each with `src` (the picture file) and `caption`.

## If the site does not update after a change

GitHub sends an email when a build fails. The site then keeps showing the last version that worked. The usual causes:

- a `{% include ... %}` line with a missing quote or bracket;
- the settings block at the top of a file: each line is `name: value`, indented with spaces, and text that contains a colon needs double quotes around it.

The "Actions" tab of the repository shows the error message. Correcting the line, or putting back the earlier text (the "History" button of a file shows every earlier version), brings the site back.

## Moving from Jimdo: the remaining steps

Pictures that have not been copied yet are written as `IMPORT:name` in the page files and show as grey boxes.

1. **Copy pictures and PDFs.** While the Jimdo site is still online, run the import once. Either on github.com: "Actions" tab, "Import pictures and PDFs from Jimdo", "Run workflow". Or on a computer with Python 3, in a copy of this repository: `python3 tools/import_from_jimdo.py`, then commit and push. The script saves a copy of every Jimdo page in `tools/jimdo-snapshot/`, downloads the files, fills the picture slots where it can do so with certainty, and writes a comparison of the old and new text to `tools/jimdo-snapshot/text-check.txt`.
2. **Check the test address.** With Pages switched on (repository "Settings", "Pages", "Deploy from a branch", branch `main`, folder `/ (root)`), the site is at `https://alicegabriel.github.io/`.
3. **Move the domain.** Transfer `alicegabriel.com` from Jimdo to another registrar. At the new registrar set these DNS records:

   | Type | Name | Value |
   | --- | --- | --- |
   | A | `@` | `185.199.108.153` |
   | A | `@` | `185.199.109.153` |
   | A | `@` | `185.199.110.153` |
   | A | `@` | `185.199.111.153` |
   | AAAA (optional) | `@` | `2606:50c0:8000::153`, `2606:50c0:8001::153`, `2606:50c0:8002::153`, `2606:50c0:8003::153` |
   | CNAME | `www` | `alicegabriel.github.io` |

   Enter `www.alicegabriel.com` under "Settings", "Pages", "Custom domain" before changing the DNS records. GitHub then adds a file named `CNAME` to this repository. Do not add that file earlier: with it in place the test address stops working. Tick "Enforce HTTPS" once GitHub offers it, which can take up to a day.
4. **Cancel the Jimdo plan** after the site has run from GitHub for a few days. Moving the domain does not cancel the plan.
5. Afterwards the folder `tools/` and the file `.github/workflows/import-from-jimdo.yml` can be deleted.

## Fonts

The site uses IBM Plex Sans and IBM Plex Serif, served from `assets/fonts/` under the SIL Open Font License (the licence texts are in that folder).
