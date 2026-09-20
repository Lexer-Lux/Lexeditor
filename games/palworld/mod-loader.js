    function palworldModLoaderSection(){return LexeditorUI.modLoaderSection({
      loader:"Pocketpair official mod loader; PalSchema is needed for raw table patches.",
      output:"Builds an official package; local testing copies it to an owned Workshop folder.",
      order:"The game manages client activation. Dedicated-server activation is an explicit config change.",
      safety:"Refuses unowned or externally changed deployment files. Does not edit game archives.",
      removal:"Undo server activation before removing the owned deployment; project sources remain."
    });}
