import { DefaultType, registerFileAction } from '@nextcloud/files'
import { generateUrl } from '@nextcloud/router'
import { translate as t } from '@nextcloud/l10n'

const fileAction = {
    id: 'ncgrisbi',
    order: 1,
    default: DefaultType.DEFAULT,
    displayName: () => t('ncgrisbi', 'Open With NCGrisbi'),
    iconSvgInline() {
        return '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="200" height="200" version="1.0"><defs><linearGradient id="L"><stop offset="0" style="stop-color:#3b4d7f"/><stop offset="1" style="stop-color:#5a92b8"/></linearGradient></defs><rect style="fill:url(#L)" width="200" height="200"/><path style="fill:#fff;fill-opacity:.1" d="M0 0h200v200H0z"/><circle cx="100" cy="100" r="45" style="fill:none;stroke:#fff;stroke-width:8"/><path style="fill:#fff" d="M100 70l12 36h38l-31 22 12 36-31-22-31 22 12-36-31-22h38z"/></svg>'
    },
    enabled: ({ nodes }) => {
        return nodes.filter((node) => node.mime === "application/x-gsb").length > 0
    },
    exec: async ({ nodes }) => {
        // Handle the first selected node with .gsb extension
        const node = nodes[0]
        if (node && node.mime === "application/x-gsb") {
            // Build the URL with proper encoding
            const encodedPath = encodeURIComponent(node.path)
            const url = generateUrl('/apps/ncgrisbi/file?open=' + encodedPath)
            // Use window.location.href for NC33+
            window.location.href = url
        }
    },
}

registerFileAction(fileAction)
