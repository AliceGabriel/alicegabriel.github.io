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
![Short description of the picture](/assets/img/home/my-picture.jpg)

### Title of the news item

Text of the news item, with [a link](https://example.org).

***
```

The line with three asterisks separates news items. Keep an empty line above and below it. A news item can go without a picture. The words in the square brackets describe the picture for people who cannot see it. They do not appear on the page.

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

The page shows a still picture. The video plays in place after a click, so nothing loads from YouTube before that.

The still picture is the file `assets/img/video/` plus the id plus `.jpg`, for example `assets/img/video/JpwcWkPuc9A.jpg`. For a new video, save one frame of it under that name (wide format, 16:9). Without that file the still comes from YouTube's picture server, which works but contacts YouTube when the page opens.

The three videos at the top of the home page are listed in the settings block of `index.md` under `videos:`.

### Change the group photos on the Team page

They are listed in the settings block of `team.md` under `photos:`, each with `src` (the picture file) and `caption`.

### Quotation marks and dashes

They appear on the site exactly as typed. A straight `"` stays straight, a curly `“` stays curly.

## If the site does not update after a change

GitHub sends an email when a build fails. The site then keeps showing the last version that worked. The usual causes:

- a `{% include ... %}` line with a missing quote or bracket;
- the settings block at the top of a file: each line is `name: value`, indented with spaces, and text that contains a colon needs double quotes around it.

The "Actions" tab of the repository shows the error message. Correcting the line, or putting back the earlier text (the "History" button of a file shows every earlier version), brings the site back.

## Moving from Jimdo: the remaining steps

1. **Copy pictures and PDFs.** Done in October 2026. The paper PDFs are in `assets/papers/`, the CV in `assets/files/`, the pictures in `assets/img/`, the video stills in `assets/img/video/`.
   - The eight Jimdo pages as saved from a browser on 10 October 2026 are in `tools/jimdo-snapshot/pages/`. They are the record of the old site. `tools/jimdo-snapshot/text-check.txt` lists the differences between their text and the new pages.
   - To copy again after a change on the Jimdo site: save the changed page from a browser ("Save Page As") over the file of the same name in that folder, then run the import on github.com: "Actions" tab, "Import pictures and PDFs from Jimdo", "Run workflow". Jimdo's page server turns away requests from GitHub, which is why the import works from saved pages. What a run printed is kept in `tools/jimdo-snapshot/import-log.txt`.
2. **Check the test address.** GitHub publishes the site at `https://alicegabriel.github.io/` once the repository is public and Pages is switched on (repository "Settings", "Pages", "Deploy from a branch", branch `main`, folder `/ (root)`). A private repository is published only on a paid GitHub plan.
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
