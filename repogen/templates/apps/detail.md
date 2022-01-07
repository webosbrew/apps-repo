Title: {{title}}
Status: hidden
Save_As: apps/{{id}}.html
Template: app

<img src="{{iconUri}}" class="app-icon" alt="{{title}} Icon" />

Version: {{manifest.version}}

{{#manifest.sourceUrl}}Source: [{{manifest.sourceUrl}}]({{manifest.sourceUrl}}){{/manifest.sourceUrl}}

{{#lastmodified}}Last Updated: {{lastmodified}}{{/lastmodified}}

---

{{&description}}
