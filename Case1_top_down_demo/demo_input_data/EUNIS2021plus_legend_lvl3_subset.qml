<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.34.0" styleCategories="AllStyleCategories">
  <flags>
    <Identifiable>1</Identifiable>
    <Removable>1</Removable>
    <Searchable>1</Searchable>
    <Private>0</Private>
  </flags>
  <temporal fetchMode="0" enabled="0" mode="0">
    <fixedRange><start></start><end></end></fixedRange>
  </temporal>
  <pipe-data-defined-properties>
    <Option type="Map">
      <Option value="" type="QString" name="name"/>
      <Option name="properties"/>
      <Option value="collection" type="QString" name="type"/>
    </Option>
  </pipe-data-defined-properties>
  <pipe>
    <provider>
      <resampling enabled="false" maxOversampling="2" zoomedInResamplingMethod="nearestNeighbour" zoomedOutResamplingMethod="nearestNeighbour"/>
    </provider>
    <rasterrenderer alphaBand="-1" band="1" nodataColor="" opacity="1" type="paletted">
      <rasterTransparency/>
      <minMaxOrigin>
        <limits>None</limits>
        <extent>WholeRaster</extent>
        <statAccuracy>Estimated</statAccuracy>
        <cumulativeCutLower>0.02</cumulativeCutLower>
        <cumulativeCutUpper>0.98</cumulativeCutUpper>
        <stdDevFactor>2</stdDevFactor>
      </minMaxOrigin>
      <colorPalette>
        <paletteEntry alpha="255" color="#76DDF7" label="N1D" value="40113"/>
        <paletteEntry alpha="255" color="#32B7B4" label="N1H" value="40117"/>
        <paletteEntry alpha="255" color="#084877" label="N1J" value="40118"/>
        <paletteEntry alpha="255" color="#E676F7" label="Q21" value="50201"/>
        <paletteEntry alpha="255" color="#CE65E9" label="Q22" value="50202"/>
        <paletteEntry alpha="255" color="#D255DB" label="Q24" value="50204"/>
        <paletteEntry alpha="255" color="#A946CC" label="Q41" value="50401"/>
        <paletteEntry alpha="255" color="#BE39BE" label="Q42" value="50402"/>
        <paletteEntry alpha="255" color="#842DB0" label="Q43" value="50403"/>
        <paletteEntry alpha="255" color="#A22299" label="Q44" value="50404"/>
        <paletteEntry alpha="255" color="#621894" label="Q51" value="50501"/>
        <paletteEntry alpha="255" color="#861076" label="Q52" value="50502"/>
        <paletteEntry alpha="255" color="#440977" label="Q53" value="50503"/>
        <paletteEntry alpha="255" color="#BBF776" label="R1A" value="60110"/>
        <paletteEntry alpha="255" color="#B4EB66" label="R1M" value="60121"/>
        <paletteEntry alpha="255" color="#98E058" label="R1P" value="60123"/>
        <paletteEntry alpha="255" color="#A3D44A" label="R21" value="60201"/>
        <paletteEntry alpha="255" color="#78C83D" label="R22" value="60202"/>
        <paletteEntry alpha="255" color="#93BD31" label="R35" value="60305"/>
        <paletteEntry alpha="255" color="#59B126" label="R36" value="60306"/>
        <paletteEntry alpha="255" color="#84A61D" label="R37" value="60307"/>
        <paletteEntry alpha="255" color="#3D9A14" label="R52" value="60502"/>
        <paletteEntry alpha="255" color="#768F0C" label="R54" value="60504"/>
        <paletteEntry alpha="255" color="#258305" label="R55" value="60505"/>
        <paletteEntry alpha="255" color="#677700" label="R57" value="60507"/>
        <paletteEntry alpha="255" color="#F7C476" label="S22" value="70202"/>
        <paletteEntry alpha="255" color="#E29F5A" label="S32" value="70302"/>
        <paletteEntry alpha="255" color="#CCA241" label="S35" value="70305"/>
        <paletteEntry alpha="255" color="#B7652C" label="S37" value="70307"/>
        <paletteEntry alpha="255" color="#A28619" label="S41" value="70401"/>
        <paletteEntry alpha="255" color="#8D340B" label="S42" value="70402"/>
        <paletteEntry alpha="255" color="#776A00" label="S92" value="70902"/>
        <paletteEntry alpha="255" color="#76F7AC" label="T12" value="80102"/>
        <paletteEntry alpha="255" color="#63E992" label="T13" value="80103"/>
        <paletteEntry alpha="255" color="#51DB94" label="T16" value="80106"/>
        <paletteEntry alpha="255" color="#41CC69" label="T17" value="80107"/>
        <paletteEntry alpha="255" color="#32BE80" label="T19" value="80109"/>
        <paletteEntry alpha="255" color="#25B044" label="T1B" value="80111"/>
        <paletteEntry alpha="255" color="#19A26E" label="T1E" value="80114"/>
        <paletteEntry alpha="255" color="#0F9424" label="T1F" value="80115"/>
        <paletteEntry alpha="255" color="#07865E" label="T27" value="80207"/>
        <paletteEntry alpha="255" color="#00770A" label="T3M" value="80321"/>
        <paletteEntry alpha="255" color="#F7CE76" label="U23" value="90203"/>
        <paletteEntry alpha="255" color="#CC9355" label="U27" value="90207"/>
        <paletteEntry alpha="255" color="#A29239" label="U37" value="90307"/>
        <paletteEntry alpha="255" color="#774023" label="U38" value="90308"/>
        <paletteEntry alpha="255" color="#F4F776" label="V11" value="100101"/>
        <paletteEntry alpha="255" color="#E7DF61" label="V13" value="100103"/>
        <paletteEntry alpha="255" color="#CAD74D" label="V15" value="100105"/>
        <paletteEntry alpha="255" color="#C7B53B" label="V1x" value="100106"/>
        <paletteEntry alpha="255" color="#A0B72C" label="V34" value="100304"/>
        <paletteEntry alpha="255" color="#A78B1E" label="V35" value="100305"/>
        <paletteEntry alpha="255" color="#779712" label="V37" value="100307"/>
        <paletteEntry alpha="255" color="#876408" label="V38" value="100308"/>
        <paletteEntry alpha="255" color="#527700" label="V39" value="100309"/>
        <paletteEntry alpha="255" color="#17e2db" label="C" value="110000"/>
        <paletteEntry alpha="255" color="#a5a5a6" label="J" value="120000"/>
      </colorPalette>
      <colorramp name="[source]" type="randomcolors">
        <Option/>
      </colorramp>
    </rasterrenderer>
    <brightnesscontrast brightness="0" contrast="0" gamma="1"/>
    <huesaturation colorizeBlue="128" colorizeGreen="128" colorizeOn="0" colorizeRed="255" colorizeStrength="100" grayscaleMode="0" invertColors="0" saturation="0"/>
    <rasterresampler maxOversampling="2"/>
    <resamplingStage>resamplingFilter</resamplingStage>
  </pipe>
  <blendMode>0</blendMode>
  <vectorjoins/>
  <layerGeometryType>4</layerGeometryType>
</qgis>
