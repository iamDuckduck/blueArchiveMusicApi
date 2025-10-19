package com.ba.bluearchivemusicapi.service;

import com.ba.bluearchivemusicapi.dtos.OstTypeDTO;
import com.ba.bluearchivemusicapi.entities.OstType;
import com.ba.bluearchivemusicapi.mappers.OstTypeMapper;
import com.ba.bluearchivemusicapi.repositories.OstTypeRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class OstTypeService {
    private final OstTypeRepository ostTypeRepository;

    private final OstTypeMapper ostTypeMapper;

    public List<OstTypeDTO> getAll() {
        Iterable<OstType> ostTypes = ostTypeRepository.findAllByOrderByVolumeAsc();
        return ostTypeMapper.toDTOList(ostTypes);
    }
}
