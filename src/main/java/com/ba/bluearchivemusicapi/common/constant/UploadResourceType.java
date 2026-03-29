package com.ba.bluearchivemusicapi.common.constant;

public enum UploadResourceType {
    ALBUM("album/coverImages", null),
    SONG("song/coverImages", "song/audio");

    public final String coverImagePath;
    public final String audioPath;

    UploadResourceType(String coverImagePath, String audioPath) {
        this.coverImagePath = coverImagePath;
        this.audioPath = audioPath;
    }
}
