# name: import block
# kind: snippet
# tags: meta, import
# about: Bringing something that already exists under management. The id is
#        per resource type — an ARN for one, a name for another — so check the
#        provider's documentation for which.

import {
  to = ${1:terraform_data.name}
  id = "${2:the-existing-id}"
}
