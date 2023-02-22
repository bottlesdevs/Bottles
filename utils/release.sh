#!/usr/bin/env bash
VER=$(cat ./VERSION)
echo "- Current version: ${VER}"
echo -n "New version (e.g 50.0): "
read -r NEW_VER

echo "- Updating ./VERSION"
echo -n "$NEW_VER" >./VERSION

echo "- Updating ./meson.build"
sed -i -e "s/version: '${VER}'/version: '${NEW_VER}'/g" ./meson.build

FILE=./data/com.usebottles.bottles.metainfo.xml.in
POS=$(grep -n "<releases>" ${FILE} | cut -f1 -d:)

echo "- Adding stub release description to ${FILE}"
sed -i -e "${POS}r /dev/stdin" ${FILE} <<EOT
        <release version="${NEW_VER}" date="$(date -Idate)">
          <description>
            <ul>
               <li>TODO: edit me</li>
               <li>TODO: edit me</li>
               <li>TODO: edit me</li>
           </ul>
          </description>
        </release>
EOT

echo "Press Enter to edit ${FILE}"
read -r
${EDITOR:-vim} +"$POS" $FILE

echo "- Adding commit"
git add -A
git commit -m "release: ${NEW_VER}"

echo "- Tagging commit"
git tag "${NEW_VER}"

cat <<EOT
======= Release Ready =======
A new commit for release '${NEW_VER}' is created.
Push it if everything looks good

        git push --follow-tags

Otherwise revert it by

        git tag --delete ${NEW_VER} && git reset --soft HEAD~

EOT
