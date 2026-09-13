package com.ba.bluearchivemusicapi.common.exception;

import com.ba.bluearchivemusicapi.dtos.catalog.CatalogImportStateDTO;

public class CatalogConflictException extends RuntimeException {
    private final CatalogImportStateDTO current;

    public CatalogConflictException(CatalogImportStateDTO current) {
        super("Published content changed. Compare the current catalog with your draft before accepting a new baseline and publishing again.");
        this.current = current;
    }

    public CatalogImportStateDTO getCurrent() { return current; }
}
